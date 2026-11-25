"""Factory configuration loaded from a TOML file (see ``configs/``)."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Target:
    name: str
    url: str
    ref: str
    base_commit: str
    language: str
    license: str
    source_dirs: tuple[str, ...]
    tests_dir: str
    docker_base: str
    install: str
    env: dict[str, str] = field(default_factory=dict)
    feature_test_prefix: str = "test_tv_"


@dataclass(frozen=True)
class Factory:
    num_tasks: int
    org: str
    axes: tuple[str, ...]
    max_repair_rounds: int = 2
    max_symbol_jaccard: float = 0.34
    max_text_similarity: float = 0.55
    mutants_per_task: int = 16
    min_mutation_score: float = 0.7
    oracle_repeats: int = 3
    author_name: str = "Trinetra Soft"
    author_email: str = "info@trinetrasoft.com"


@dataclass(frozen=True)
class Generation:
    provider: str = "replay"
    model: str = "claude-opus-5-5"
    cache_dir: str = "cache/llm"
    pending_dir: str = "cache/pending"
    temperature: float = 0.2


@dataclass(frozen=True)
class Config:
    path: Path
    target: Target
    factory: Factory
    generation: Generation
    workdir: Path
    output: Path

    @property
    def root(self) -> Path:
        return self.path.parent.parent


def load(path: str | Path, *, provider: str | None = None) -> Config:
    path = Path(path).resolve()
    data = tomllib.loads(path.read_text())
    t = data["target"]
    target = Target(
        name=t["name"],
        url=t["url"],
        ref=t["ref"],
        base_commit=t["base_commit"],
        language=t["language"],
        license=t["license"],
        source_dirs=tuple(t["source_dirs"]),
        tests_dir=t.get("tests_dir", "tests"),
        docker_base=t["docker_base"],
        install=t["install"],
        env=dict(t.get("env", {})),
        feature_test_prefix=t.get("feature_test_prefix", "test_tv_"),
    )
    f = data["factory"]
    factory = Factory(
        num_tasks=int(f["num_tasks"]),
        org=f["org"],
        axes=tuple(f["axes"]),
        max_repair_rounds=int(f.get("max_repair_rounds", 2)),
        max_symbol_jaccard=float(f.get("max_symbol_jaccard", 0.34)),
        max_text_similarity=float(f.get("max_text_similarity", 0.55)),
        mutants_per_task=int(f.get("mutants_per_task", 16)),
        min_mutation_score=float(f.get("min_mutation_score", 0.7)),
        oracle_repeats=int(f.get("oracle_repeats", 3)),
        author_name=f.get("author_name", "Trinetra Soft"),
        author_email=f.get("author_email", "info@trinetrasoft.com"),
    )
    g = data.get("generation", {})
    generation = Generation(
        provider=provider or g.get("provider", "replay"),
        model=g.get("model", "claude-opus-5-5"),
        cache_dir=g.get("cache_dir", "cache/llm"),
        pending_dir=g.get("pending_dir", "cache/pending"),
        temperature=float(g.get("temperature", 0.2)),
    )
    root = path.parent.parent
    p = data.get("paths", {})
    return Config(
        path=path,
        target=target,
        factory=factory,
        generation=generation,
        workdir=(root / p.get("workdir", ".triverify")).resolve(),
        output=(root / p.get("output", "output")).resolve(),
    )
