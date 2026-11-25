"""Git plumbing: pinned checkouts, disposable worktrees and patch handling."""

from __future__ import annotations

import contextlib
import shutil
import subprocess
import tempfile
from collections.abc import Iterator
from pathlib import Path

from .config import Config


class GitError(RuntimeError):
    pass


def git(*args: str, cwd: Path | str, check: bool = True, input: str | None = None) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, input=input
    )
    if check and proc.returncode != 0:
        raise GitError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout


def ensure_base(cfg: Config) -> Path:
    """Clone the target repository once and verify the pinned base commit.

    The full history is fetched so the factory can check that a generated
    feature does not already exist upstream (``origin/main``).
    """
    base = cfg.workdir / "repos" / cfg.target.name
    if not (base / ".git").exists():
        base.parent.mkdir(parents=True, exist_ok=True)
        git("clone", "--quiet", cfg.target.url, str(base), cwd=base.parent)
    else:
        git("fetch", "--quiet", "--tags", "origin", cwd=base, check=False)
    git("checkout", "--quiet", "--detach", cfg.target.base_commit, cwd=base)
    head = git("rev-parse", "HEAD", cwd=base).strip()
    if head != cfg.target.base_commit:
        raise GitError(f"base commit mismatch: {head} != {cfg.target.base_commit}")
    tag_commit = git("rev-list", "-n", "1", cfg.target.ref, cwd=base, check=False).strip()
    if tag_commit and tag_commit != cfg.target.base_commit:
        raise GitError(
            f"ref {cfg.target.ref} points to {tag_commit}, config pins {cfg.target.base_commit}"
        )
    return base


@contextlib.contextmanager
def worktree(base: Path, commit: str) -> Iterator[Path]:
    """A throw-away copy of the repository at ``commit``."""
    tmp = Path(tempfile.mkdtemp(prefix="tv-wt-"))
    path = tmp / "repo"
    try:
        git("worktree", "add", "--quiet", "--detach", str(path), commit, cwd=base)
        yield path
    finally:
        git("worktree", "remove", "--force", str(path), cwd=base, check=False)
        shutil.rmtree(tmp, ignore_errors=True)


def apply_patch(repo: Path, patch: str, *, check_only: bool = False) -> None:
    args = ["apply", "--whitespace=nowarn"]
    if check_only:
        args.append("--check")
    git(*args, "-", cwd=repo, input=patch)


def changed_lines(patch: str) -> dict[str, set[int]]:
    """Return ``{path: {new-file line numbers added or modified}}`` for a diff."""
    result: dict[str, set[int]] = {}
    current: str | None = None
    new_line = 0
    for line in patch.splitlines():
        if line.startswith("+++ "):
            name = line[4:].strip()
            current = None if name == "/dev/null" else name.removeprefix("b/")
            if current:
                result.setdefault(current, set())
        elif line.startswith("@@"):
            # @@ -a,b +c,d @@
            plus = line.split("+", 1)[1].split(" ", 1)[0]
            new_line = int(plus.split(",")[0])
        elif current is None:
            continue
        elif line.startswith("+") and not line.startswith("+++"):
            result[current].add(new_line)
            new_line += 1
        elif line.startswith("-") and not line.startswith("---"):
            continue
        elif line.startswith("\\"):
            continue
        else:
            new_line += 1
    return result


def upstream_mentions(base: Path, identifiers: list[str], paths: tuple[str, ...]) -> dict[str, list[str]]:
    """Find identifiers that already exist on ``origin/main`` (novelty check)."""
    hits: dict[str, list[str]] = {}
    for ident in identifiers:
        out = git(
            "grep", "-n", "-w", "-F", ident, "origin/main", "--", *paths, cwd=base, check=False
        )
        lines = [ln for ln in out.splitlines() if ln.strip()]
        if lines:
            hits[ident] = lines[:5]
    return hits
