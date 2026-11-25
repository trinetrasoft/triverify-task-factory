"""Proposal → authoring → repair stages (model-driven, cache-backed)."""

from __future__ import annotations

import ast
import json
from importlib import resources
from pathlib import Path

from . import analysis
from .config import Config
from .llm import Provider, extract_json, prompt_key

REQUIRED_SPEC_KEYS = (
    "id",
    "title",
    "axis",
    "instruction",
    "solution_patch",
    "feature_tests",
    "public_api",
)


def _template(name: str) -> str:
    return resources.files("triverify.prompts").joinpath(name).read_text(encoding="utf-8")


def build_propose_prompt(cfg: Config, base: Path) -> str:
    cmap = analysis.capability_map(base, cfg.target.source_dirs, cfg.target.tests_dir)
    return _template("propose.md").format(
        repo_url=cfg.target.url,
        base_commit=cfg.target.base_commit,
        ref=cfg.target.ref,
        language=cfg.target.language,
        capability_map=analysis.render_capability_map(cmap),
        num_tasks=cfg.factory.num_tasks,
        axes="; ".join(cfg.factory.axes),
    )


def propose(cfg: Config, provider: Provider, base: Path) -> tuple[list[dict], dict]:
    prompt = build_propose_prompt(cfg, base)
    data = extract_json(provider.complete("propose", prompt))
    proposals = data["proposals"]
    if len(proposals) != cfg.factory.num_tasks:
        raise ValueError(f"expected {cfg.factory.num_tasks} proposals, got {len(proposals)}")
    axes = [p["axis"] for p in proposals]
    if len(set(axes)) != len(axes):
        raise ValueError(f"proposals reuse a variation axis: {axes}")
    unknown = [a for a in axes if a not in cfg.factory.axes]
    if unknown:
        raise ValueError(f"proposals use unknown axes: {unknown}")
    provenance = {"stage": "propose", "key": prompt_key("propose", provider.model, prompt)}
    return proposals, provenance


def _segments(path: Path, keywords: set[str], max_lines: int = 650) -> str:
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines()
    if len(lines) <= max_lines:
        return source
    tree = ast.parse(source)
    picked: list[tuple[int, int, str]] = []
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name in keywords:
            picked.append((node.lineno, node.end_lineno or node.lineno, node.name))
    if not picked:
        return "\n".join(lines[:300]) + "\n# … (truncated)"
    out = []
    for start, end, name in sorted(picked):
        out.append(f"# --- {name} (lines {start}-{end}) ---")
        out.extend(lines[start - 1 : end])
    return "\n".join(out)


def source_excerpts(base: Path, proposal: dict) -> str:
    text = " ".join(
        [proposal.get("title", ""), proposal.get("summary", ""), *proposal.get("public_api", [])]
    )
    words = {w.strip("`.,:;()[]'\"") for w in text.replace("/", " ").split()}
    words |= set(proposal.get("anchors", []))
    blocks = []
    for rel in proposal.get("touches", []):
        p = base / rel
        if p.is_file() and p.suffix == ".py":
            blocks.append(f"### {rel}\n```python\n{_segments(p, words)}\n```")
    return "\n\n".join(blocks) or "(no source excerpts)"


def build_author_prompt(cfg: Config, base: Path, proposal: dict) -> str:
    tests = sorted(
        p.relative_to(base).as_posix() for p in (base / cfg.target.tests_dir).rglob("test_*.py")
    )
    return _template("author.md").format(
        repo_url=cfg.target.url,
        base_commit=cfg.target.base_commit,
        ref=cfg.target.ref,
        language=cfg.target.language,
        test_modules=", ".join(tests),
        proposal=json.dumps(proposal, indent=2, sort_keys=True),
        source_excerpts=source_excerpts(base, proposal),
        task_id=proposal["id"],
    )


def validate_spec_shape(spec: dict) -> None:
    missing = [k for k in REQUIRED_SPEC_KEYS if not spec.get(k)]
    if missing:
        raise ValueError(f"spec {spec.get('id')} is missing {missing}")
    if "diff --git" not in spec["solution_patch"]:
        raise ValueError(f"spec {spec['id']} solution_patch is not a git diff")
    ast.parse(spec["feature_tests"])  # syntax gate before anything runs


def author(cfg: Config, provider: Provider, base: Path, proposal: dict) -> dict:
    prompt = build_author_prompt(cfg, base, proposal)
    spec = extract_json(provider.complete("author", prompt))
    spec["id"] = proposal["id"]
    validate_spec_shape(spec)
    spec["provenance"] = [
        {"stage": "author", "key": prompt_key("author", provider.model, prompt), "model": provider.model}
    ]
    return spec


def repair(cfg: Config, provider: Provider, spec: dict, failures: list[str], round_no: int) -> dict:
    package = {k: spec[k] for k in (*REQUIRED_SPEC_KEYS, "difficulty", "tags") if k in spec}
    prompt = _template("repair.md").format(
        repo_url=cfg.target.url,
        base_commit=cfg.target.base_commit,
        ref=cfg.target.ref,
        package=json.dumps(package, indent=2, sort_keys=True),
        failures="\n".join(f"- {f}" for f in failures),
    )
    fixed = extract_json(provider.complete(f"repair-{round_no}", prompt))
    fixed["id"] = spec["id"]
    validate_spec_shape(fixed)
    fixed["provenance"] = [
        *spec.get("provenance", []),
        {
            "stage": f"repair-{round_no}",
            "key": prompt_key(f"repair-{round_no}", provider.model, prompt),
            "model": provider.model,
            "failures": failures,
        },
    ]
    return fixed
