"""Local triple verification of a task spec (the factory's quality gate).

Gate 1 – NOP:     starting commit + feature tests → every feature test fails,
                  every pass-to-pass test passes (expected reward 0.0).
Gate 2 – ORACLE:  reference patch applied → everything passes, ``oracle_repeats``
                  times in a row (expected reward 1.0, no flakiness).
Gate 3 – MUTANTS: mutants of the patch's added lines must be caught by the
                  feature tests (mutation score ≥ ``min_mutation_score``).
Plus static gates: patch applies cleanly, no instruction leakage, and the
feature's public names do not already exist upstream.

All runs use the same reward function as the Harbor verifier
(:mod:`triverify.grading`).
"""

from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from . import analysis, grading, mutate
from .config import Config
from .repo import apply_patch, changed_lines, upstream_mentions, worktree


def target_python(cfg: Config) -> str:
    """Python interpreter used to run the target's tests (``TRIVERIFY_TARGET_PYTHON``)."""
    return os.environ.get("TRIVERIFY_TARGET_PYTHON", sys.executable)


def feature_module(cfg: Config, spec_id: str) -> str:
    stem = cfg.target.feature_test_prefix + re.sub(r"[^a-z0-9]+", "_", spec_id.lower()).strip("_")
    return stem


def is_feature(test_id: str, prefix: str) -> bool:
    """True if a JUnit test id belongs to the feature module ``prefix``."""
    cls = test_id.split("::", 1)[0]
    return cls == prefix or cls.startswith(prefix + ".")


def _run(cfg: Config, repo: Path, targets: list[str]) -> tuple[dict[str, str], float, str]:
    with tempfile.TemporaryDirectory() as tmp:
        junit = Path(tmp) / "junit.xml"
        start = time.monotonic()
        proc = grading.run_pytest(
            repo, targets, junit, env=cfg.target.env, python=target_python(cfg)
        )
        elapsed = time.monotonic() - start
        return grading.junit_outcomes(junit), elapsed, (proc.stdout + proc.stderr)[-4000:]


def baseline(cfg: Config, base: Path, runs: int = 2) -> dict:
    """Pass-to-pass set: tests that pass on the starting commit in every run."""
    passing: set[str] | None = None
    durations = []
    total = 0
    for _ in range(runs):
        with worktree(base, cfg.target.base_commit) as wt:
            outcomes, elapsed, _ = _run(cfg, wt, [cfg.target.tests_dir])
        durations.append(round(elapsed, 2))
        total = len(outcomes)
        ok = {t for t, o in outcomes.items() if o == grading.PASSED}
        passing = ok if passing is None else passing & ok
    return {
        "pass_to_pass": sorted(passing or ()),
        "collected": total,
        "runs": runs,
        "durations_sec": durations,
    }


def _leakage(spec: dict) -> list[str]:
    problems = []
    instr = spec["instruction"]
    added = [
        ln[1:].strip()
        for ln in spec["solution_patch"].splitlines()
        if ln.startswith("+") and not ln.startswith("+++")
    ]
    declaration = re.compile(r"^[A-Za-z_]\w*\s*:\s*[^=()]+(=\s*[^,()]+)?,?$")
    for line in added:
        if declaration.match(line):  # a parameter declaration the spec must state anyway
            continue
        if len(line) >= 28 and not line.startswith(("#", '"""', "'''")) and line in instr:
            problems.append(f"instruction contains solution line: {line[:60]!r}")
    if re.search(r"test_tv_|fail_to_pass|pass_to_pass|feature_tests", instr):
        problems.append("instruction refers to the hidden tests")
    return problems


def validate(cfg: Config, base: Path, spec: dict, p2p: list[str]) -> dict:
    module = feature_module(cfg, spec["id"])
    test_rel = f"{cfg.target.tests_dir}/{module}.py"
    prefix = f"{cfg.target.tests_dir}.{module}"
    report: dict = {"id": spec["id"], "feature_module": test_rel, "gates": {}, "failures": []}
    fail = report["failures"]

    # Static: patch applies, leakage, novelty upstream.
    with worktree(base, cfg.target.base_commit) as wt:
        try:
            apply_patch(wt, spec["solution_patch"], check_only=True)
            report["gates"]["patch_applies"] = True
        except Exception as exc:  # noqa: BLE001 - report everything
            report["gates"]["patch_applies"] = False
            fail.append(f"patch_applies: {exc}")
            return report
    leaks = _leakage(spec)
    report["gates"]["no_leakage"] = not leaks
    fail.extend(f"no_leakage: {p}" for p in leaks)
    upstream = upstream_mentions(base, list(spec.get("public_api", [])), cfg.target.source_dirs)
    report["upstream_hits"] = upstream
    report["gates"]["novel_upstream"] = not upstream
    if upstream:
        fail.append(f"novel_upstream: already on origin/main: {sorted(upstream)}")

    # Gate 2 first (discovers the feature test ids), repeated for flakiness.
    oracle_runs = []
    f2p: list[str] = []
    for i in range(cfg.factory.oracle_repeats):
        with worktree(base, cfg.target.base_commit) as wt:
            apply_patch(wt, spec["solution_patch"])
            (wt / test_rel).write_text(spec["feature_tests"])
            outcomes, elapsed, tail = _run(cfg, wt, [cfg.target.tests_dir])
            if i == 0:
                f2p = sorted(t for t in outcomes if is_feature(t, prefix))
                patched = {}
                for path, lines in changed_lines(spec["solution_patch"]).items():
                    if path.endswith(".py") and (wt / path).exists():
                        patched[path] = ((wt / path).read_text(), lines)
        res = grading.compute_reward(outcomes, f2p, p2p)
        oracle_runs.append(
            {"reward": res["reward"], "seconds": round(elapsed, 2), "regressions": res["regressions"][:10],
             "features_failed": res["features_failed"][:10], "log_tail": "" if res["reward"] == 1.0 else tail}
        )
    report["fail_to_pass"] = f2p
    report["oracle"] = oracle_runs
    ok_oracle = bool(f2p) and all(r["reward"] == 1.0 for r in oracle_runs)
    report["gates"]["oracle_reward_1"] = ok_oracle
    if not f2p:
        fail.append("oracle_reward_1: no feature tests were collected")
    elif not ok_oracle:
        bad = next(r for r in oracle_runs if r["reward"] != 1.0)
        fail.append(
            f"oracle_reward_1: reward {bad['reward']}; failing features {bad['features_failed']}; "
            f"regressions {bad['regressions']}; log: {bad['log_tail'][-1500:]}"
        )
    n_tests = len(f2p)
    report["gates"]["test_count_6_14"] = 6 <= n_tests <= 14
    if not 6 <= n_tests <= 14:
        fail.append(f"test_count_6_14: {n_tests} feature tests")

    # Gate 1: starting commit + feature tests.
    with worktree(base, cfg.target.base_commit) as wt:
        (wt / test_rel).write_text(spec["feature_tests"])
        outcomes, elapsed, _ = _run(cfg, wt, [cfg.target.tests_dir])
    nop = grading.compute_reward(outcomes, f2p, p2p)
    passing_at_base = [t for t in f2p if outcomes.get(t) == grading.PASSED]
    report["nop"] = {"reward": nop["reward"], "seconds": round(elapsed, 2),
                     "regressions": nop["regressions"][:10], "features_passing_at_base": passing_at_base}
    ok_nop = nop["reward"] == 0.0 and not nop["regressions"] and not passing_at_base
    report["gates"]["nop_reward_0"] = ok_nop
    if passing_at_base:
        fail.append(f"nop_reward_0: tests pass without the feature: {passing_at_base}")
    if nop["regressions"]:
        fail.append(f"nop_reward_0: regressions at base: {nop['regressions'][:5]}")

    # Gate 3: mutation testing on the patch's added lines.
    report["mutation"] = run_mutation(cfg, base, spec, test_rel, prefix, patched if f2p else {})
    score = report["mutation"]["score"]
    report["gates"]["mutation_score"] = score is not None and score >= cfg.factory.min_mutation_score
    if score is None or score < cfg.factory.min_mutation_score:
        survivors = [f"{m['path']}:{m['line']} {m['description']}" for m in report["mutation"]["mutants"] if not m["killed"]]
        fail.append(f"mutation_score: {score} < {cfg.factory.min_mutation_score}; survivors: {survivors[:8]}")

    # Variation evidence.
    symbols: set[str] = set()
    for path, (src, lines) in (patched if f2p else {}).items():
        try:
            symbols |= {f"{path}:{s}" for s in analysis.enclosing_symbols(src, lines)}
        except SyntaxError:
            pass
    report["touched_symbols"] = sorted(symbols)
    report["api_refs"] = sorted(analysis.referenced_api(spec["feature_tests"], "click"))
    report["passed"] = all(report["gates"].values())
    return report


def run_mutation(cfg: Config, base: Path, spec: dict, test_rel: str, prefix: str, patched: dict) -> dict:
    mutants: list[mutate.Mutant] = []
    per_file = max(1, cfg.factory.mutants_per_task // max(1, len(patched)))
    for path, (src, lines) in sorted(patched.items()):
        mutants.extend(mutate.generate(path, src, lines, per_file))
    mutants = mutate.spread(mutants, cfg.factory.mutants_per_task)
    results = []
    control_ok = True
    with worktree(base, cfg.target.base_commit) as wt:
        apply_patch(wt, spec["solution_patch"])
        (wt / test_rel).write_text(spec["feature_tests"])
        originals = {p: (wt / p).read_text() for p in patched}
        # Control: the unparse round-trip of the unmutated module must still pass.
        for p, src in originals.items():
            (wt / p).write_text(ast.unparse(ast.parse(src)))
        outcomes, _, _ = _run(cfg, wt, [test_rel])
        control_ok = bool(outcomes) and all(o == grading.PASSED for t, o in outcomes.items() if is_feature(t, prefix))
        for p, src in originals.items():
            (wt / p).write_text(src)
        for m in mutants:
            (wt / m.path).write_text(m.source)
            try:
                outcomes, elapsed, _ = _run(cfg, wt, [test_rel])
                feature = {t: o for t, o in outcomes.items() if is_feature(t, prefix)}
                killed = (not feature) or any(o != grading.PASSED for o in feature.values())
                killers = sorted(t.split("::", 1)[1] for t, o in feature.items() if o != grading.PASSED)[:4]
            except subprocess.TimeoutExpired:
                killed, killers, elapsed = True, ["<timeout>"], 0.0
            (wt / m.path).write_text(originals[m.path])
            results.append({"path": m.path, "line": m.line, "operator": m.operator,
                            "description": m.description, "killed": killed, "killed_by": killers})
    n = len(results)
    killed = sum(r["killed"] for r in results)
    return {
        "control_passed": control_ok,
        "total": n,
        "killed": killed,
        "score": round(killed / n, 3) if n and control_ok else None,
        "mutants": results,
    }


def save(report: dict, out: Path) -> Path:
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{report['id']}.json"
    path.write_text(json.dumps(report, indent=2))
    return path
