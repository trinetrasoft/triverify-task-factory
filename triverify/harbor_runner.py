"""Run the official Harbor validation matrix on generated packages.

    harbor run -p <task_dir> -a nop    -k 1 -o <out_dir> --no-delete -y   → expect 0.0
    harbor run -p <task_dir> -a oracle -k 1 -o <out_dir> --no-delete -y   → expect 1.0
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path

EXPECTED = {"nop": 0.0, "oracle": 1.0}


def available() -> bool:
    return shutil.which("harbor") is not None


def version() -> str:
    try:
        return subprocess.run(["harbor", "--version"], capture_output=True, text=True).stdout.strip()
    except OSError:
        return "unavailable"


def find_reward(out_dir: Path) -> tuple[float | None, list[str]]:
    """Read the trial reward from Harbor's job output (``result.json`` files)."""
    rewards: list[float] = []
    errors: list[str] = []
    for path in sorted(out_dir.rglob("result.json")):
        try:
            data = json.loads(path.read_text())
        except ValueError:
            continue
        vr = data.get("verifier_result")
        if isinstance(vr, dict) and isinstance(vr.get("rewards"), dict) and "reward" in vr["rewards"]:
            rewards.append(float(vr["rewards"]["reward"]))
        exc = data.get("exception_info")
        if exc:
            errors.append(str(exc)[:500])
    return (rewards[0] if rewards else None), errors


def lint(task_dir: Path) -> dict:
    """Harbor's static task checks (``harbor lint <task_dir> --json``)."""
    proc = subprocess.run(["harbor", "lint", str(task_dir), "--json"], capture_output=True, text=True)
    try:
        findings = json.loads(proc.stdout or "[]")
    except ValueError:
        findings = [{"raw": proc.stdout[-2000:]}]
    return {"exit_code": proc.returncode, "findings": findings, "stderr_tail": proc.stderr[-1500:]}


def run(task_dir: Path, agent: str, out_root: Path, timeout: int = 3600) -> dict:
    out_dir = out_root / f"{task_dir.name}-{agent}"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    cmd = ["harbor", "run", "-p", str(task_dir), "-a", agent, "-k", "1", "-o", str(out_dir), "--no-delete", "-y"]
    start = time.monotonic()
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    reward, errors = find_reward(out_dir)
    grading = next(iter(sorted(out_dir.rglob("grading.json"))), None)
    return {
        "task": task_dir.name,
        "agent": agent,
        "command": " ".join(cmd),
        "exit_code": proc.returncode,
        "seconds": round(time.monotonic() - start, 1),
        "reward": reward,
        "expected": EXPECTED[agent],
        "ok": reward is not None and reward == EXPECTED[agent],
        "errors": errors,
        "grading": json.loads(grading.read_text()) if grading else None,
        "stdout_tail": proc.stdout[-3000:],
        "stderr_tail": proc.stderr[-3000:],
    }
