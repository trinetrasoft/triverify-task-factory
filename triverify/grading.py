"""Test-result parsing and the Harbor reward formula.

This module is deliberately standard-library only: :mod:`triverify.packager`
embeds its source verbatim into every generated task as ``tests/grade.py`` so
the factory and the Harbor verifier compute rewards with *identical* code.

Reward (as specified by the Innodata guide):
    * any pass-to-pass (regression) test not passing   -> 0.0
    * otherwise                                         -> passed F2P / total F2P
A test that is missing from the report (for example because its module failed
to import) counts as not passing.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

PASSED = "passed"
FAILED = "failed"
ERROR = "error"
SKIPPED = "skipped"


def junit_outcomes(xml_path: str | os.PathLike[str]) -> dict[str, str]:
    """Map ``<classname>::<name>`` test ids to an outcome from a JUnit XML file."""
    outcomes: dict[str, str] = {}
    path = Path(xml_path)
    if not path.exists() or path.stat().st_size == 0:
        return outcomes
    root = ET.parse(path).getroot()
    for case in root.iter("testcase"):
        classname = case.get("classname", "")
        name = case.get("name", "")
        test_id = f"{classname}::{name}" if classname else name
        if case.find("failure") is not None:
            outcome = FAILED
        elif case.find("error") is not None:
            outcome = ERROR
        elif case.find("skipped") is not None:
            outcome = SKIPPED
        else:
            outcome = PASSED
        # A test reported twice (setup error + call) keeps its worst outcome.
        if outcomes.get(test_id) in (FAILED, ERROR):
            continue
        outcomes[test_id] = outcome
    return outcomes


def compute_reward(
    outcomes: dict[str, str], fail_to_pass: list[str], pass_to_pass: list[str]
) -> dict:
    """Apply the Harbor/Innodata reward formula and explain the result."""
    regressions = [t for t in pass_to_pass if outcomes.get(t) not in (PASSED, SKIPPED)]
    passed_features = [t for t in fail_to_pass if outcomes.get(t) == PASSED]
    failed_features = [t for t in fail_to_pass if outcomes.get(t) != PASSED]
    if regressions:
        reward = 0.0
    elif not fail_to_pass:
        reward = 0.0
    else:
        reward = len(passed_features) / len(fail_to_pass)
    return {
        "reward": round(reward, 6),
        "regressions": regressions,
        "features_passed": passed_features,
        "features_failed": failed_features,
        "n_fail_to_pass": len(fail_to_pass),
        "n_pass_to_pass": len(pass_to_pass),
    }


def run_pytest(
    cwd: str | os.PathLike[str],
    targets: list[str],
    junit_path: str | os.PathLike[str],
    env: dict[str, str] | None = None,
    python: str = sys.executable,
    timeout: int = 1800,
) -> subprocess.CompletedProcess:
    """Run pytest and write a JUnit report. Collection errors do not stop the run."""
    cmd = [
        python,
        "-m",
        "pytest",
        "-p",
        "no:cacheprovider",
        "-q",
        "-rN",
        "--continue-on-collection-errors",
        f"--junitxml={junit_path}",
        "-o",
        "junit_family=xunit1",
        *targets,
    ]
    full_env = {**os.environ, **(env or {})}
    return subprocess.run(
        cmd, cwd=cwd, env=full_env, capture_output=True, text=True, timeout=timeout
    )


def main(argv: list[str] | None = None) -> int:
    """Entry point used inside the Harbor container (``tests/grade.py``)."""
    import argparse

    parser = argparse.ArgumentParser(description="TriVerify grader")
    parser.add_argument("--repo", default="/app")
    parser.add_argument("--tests-dir", default="/tests")
    parser.add_argument("--out", default="/logs/verifier")
    parser.add_argument("--target", action="append", default=None)
    args = parser.parse_args(argv)

    tests_dir = Path(args.tests_dir)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    f2p = json.loads((tests_dir / "fail_to_pass.json").read_text())
    p2p = json.loads((tests_dir / "pass_to_pass.json").read_text())
    targets = args.target or ["tests"]
    junit = out / "junit.xml"

    proc = run_pytest(args.repo, targets, junit)
    (out / "pytest-stdout.txt").write_text(proc.stdout[-200_000:])
    (out / "pytest-stderr.txt").write_text(proc.stderr[-50_000:])

    result = compute_reward(junit_outcomes(junit), f2p, p2p)
    result["pytest_exit_code"] = proc.returncode
    (out / "grading.json").write_text(json.dumps(result, indent=2))
    (out / "reward.txt").write_text(f"{result['reward']}\n")
    print(
        f"reward={result['reward']} features={len(result['features_passed'])}/"
        f"{result['n_fail_to_pass']} regressions={len(result['regressions'])}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
