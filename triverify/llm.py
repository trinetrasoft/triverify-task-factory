"""Model providers with a content-addressed response cache.

Every model call is keyed by ``sha256(stage, model, prompt)`` and its response
is stored under ``cache/llm/<key>.json``. That gives the factory three modes:

* ``anthropic`` / ``openai`` – call a live API and record the response.
* ``replay``  – answer only from the cache. Deterministic, no API key needed;
  this is how judges reproduce a run bit-for-bit.
* ``handoff`` – on a cache miss, write the prompt to ``cache/pending/`` so an
  interactive coding agent (or a human) can answer it, then re-run. This is the
  mode the sample outputs in this repository were produced with (see
  ``docs/TECHNICAL.md`` → *Models and tools*).

Standard library only (``urllib``); keys are read from environment variables.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path


class CacheMiss(RuntimeError):
    def __init__(self, key: str, stage: str):
        super().__init__(f"no cached response for {stage} prompt {key}")
        self.key = key
        self.stage = stage


class PendingHandoff(CacheMiss):
    pass


def prompt_key(stage: str, model: str, prompt: str) -> str:
    h = hashlib.sha256()
    for part in (stage, model, prompt):
        h.update(part.encode("utf-8"))
        h.update(b"\x00")
    return h.hexdigest()[:24]


@dataclass
class Provider:
    model: str
    cache_dir: Path
    pending_dir: Path
    name: str = "replay"

    def _cache_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def cached(self, stage: str, prompt: str) -> str | None:
        key = prompt_key(stage, self.model, prompt)
        path = self._cache_path(key)
        if path.exists():
            return json.loads(path.read_text())["response"]
        return None

    def store(self, stage: str, prompt: str, response: str, meta: dict | None = None) -> None:
        key = prompt_key(stage, self.model, prompt)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        record = {
            "key": key,
            "stage": stage,
            "model": self.model,
            "provider": self.name,
            "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            **(meta or {}),
            "response": response,
        }
        self._cache_path(key).write_text(json.dumps(record, indent=2, ensure_ascii=False))

    def complete(self, stage: str, prompt: str) -> str:
        hit = self.cached(stage, prompt)
        if hit is not None:
            return hit
        return self._miss(stage, prompt)

    def _miss(self, stage: str, prompt: str) -> str:
        raise CacheMiss(prompt_key(stage, self.model, prompt), stage)


class ReplayProvider(Provider):
    pass


class HandoffProvider(Provider):
    """Writes unanswered prompts to ``pending_dir`` for an external agent."""

    def _miss(self, stage: str, prompt: str) -> str:
        key = prompt_key(stage, self.model, prompt)
        self.pending_dir.mkdir(parents=True, exist_ok=True)
        (self.pending_dir / f"{key}.md").write_text(
            f"<!-- triverify handoff: stage={stage} model={self.model} key={key} -->\n"
            f"<!-- Answer with the JSON object requested below and save it with\n"
            f"     `triverify answer {key} <response-file>` -->\n\n{prompt}"
        )
        raise PendingHandoff(key, stage)


class _HTTPProvider(Provider):
    url = ""
    env_key = ""

    def _headers(self, api_key: str) -> dict[str, str]:  # pragma: no cover - network
        raise NotImplementedError

    def _body(self, prompt: str) -> dict:  # pragma: no cover - network
        raise NotImplementedError

    def _text(self, payload: dict) -> str:  # pragma: no cover - network
        raise NotImplementedError

    def _miss(self, stage: str, prompt: str) -> str:  # pragma: no cover - network
        api_key = os.environ.get(self.env_key)
        if not api_key:
            raise RuntimeError(f"{self.env_key} is not set; use --provider replay or handoff")
        req = urllib.request.Request(
            self.url,
            data=json.dumps(self._body(prompt)).encode(),
            headers={"content-type": "application/json", **self._headers(api_key)},
        )
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=600) as resp:
                    payload = json.loads(resp.read())
                break
            except OSError:
                if attempt == 3:
                    raise
                time.sleep(2**attempt * 5)
        text = self._text(payload)
        self.store(stage, prompt, text, {"usage": payload.get("usage")})
        return text


class AnthropicProvider(_HTTPProvider):  # pragma: no cover - network
    url = "https://api.anthropic.com/v1/messages"
    env_key = "ANTHROPIC_API_KEY"

    def _headers(self, api_key: str) -> dict[str, str]:
        return {"x-api-key": api_key, "anthropic-version": "2023-06-01"}

    def _body(self, prompt: str) -> dict:
        return {
            "model": self.model,
            "max_tokens": 16000,
            "temperature": 0.2,
            "messages": [{"role": "user", "content": prompt}],
        }

    def _text(self, payload: dict) -> str:
        return "".join(b.get("text", "") for b in payload["content"])


class OpenAIProvider(_HTTPProvider):  # pragma: no cover - network
    url = "https://api.openai.com/v1/chat/completions"
    env_key = "OPENAI_API_KEY"

    def _headers(self, api_key: str) -> dict[str, str]:
        return {"authorization": f"Bearer {api_key}"}

    def _body(self, prompt: str) -> dict:
        return {
            "model": self.model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "user", "content": prompt}],
        }

    def _text(self, payload: dict) -> str:
        return payload["choices"][0]["message"]["content"]


PROVIDERS = {
    "replay": ReplayProvider,
    "handoff": HandoffProvider,
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
}


def make_provider(name: str, model: str, cache_dir: Path, pending_dir: Path) -> Provider:
    try:
        cls = PROVIDERS[name]
    except KeyError:
        raise ValueError(f"unknown provider {name!r}; choose from {sorted(PROVIDERS)}") from None
    return cls(model=model, cache_dir=cache_dir, pending_dir=pending_dir, name=name)


def extract_json(text: str) -> dict:
    """Parse the first JSON object in a model response (tolerates code fences)."""
    s = text.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1]
        s = s.rsplit("```", 1)[0]
    start = s.find("{")
    if start < 0:
        raise ValueError("response contains no JSON object")
    obj, _ = json.JSONDecoder().raw_decode(s[start:])
    return obj
