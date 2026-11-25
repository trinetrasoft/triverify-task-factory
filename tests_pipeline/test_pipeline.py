"""Unit tests for the factory itself (no target-repository code is executed)."""

import json
import textwrap
from pathlib import Path

import pytest

from triverify import diversity, grading, llm, mutate, repo

ROOT = Path(__file__).resolve().parents[1]


def test_reward_formula_matches_spec():
    outcomes = {"f1": "passed", "f2": "failed", "r1": "passed", "r2": "skipped"}
    assert grading.compute_reward(outcomes, ["f1", "f2"], ["r1", "r2"])["reward"] == 0.5
    outcomes["r1"] = "failed"
    assert grading.compute_reward(outcomes, ["f1", "f2"], ["r1"])["reward"] == 0.0
    # Missing tests (e.g. import error) count as not passing.
    assert grading.compute_reward({"r1": "passed"}, ["f1"], ["r1"])["reward"] == 0.0
    assert grading.compute_reward({"r1": "passed", "f1": "passed"}, ["f1"], ["r1"])["reward"] == 1.0


def test_junit_parsing(tmp_path):
    xml = tmp_path / "j.xml"
    xml.write_text(
        textwrap.dedent(
            """\
            <testsuites><testsuite>
              <testcase classname="tests.test_a" name="test_ok"/>
              <testcase classname="tests.test_a" name="test_bad[1]"><failure message="x"/></testcase>
              <testcase classname="tests.test_a" name="test_err"><error message="x"/></testcase>
              <testcase classname="tests.test_a" name="test_skip"><skipped/></testcase>
            </testsuite></testsuites>"""
        )
    )
    assert grading.junit_outcomes(xml) == {
        "tests.test_a::test_ok": "passed",
        "tests.test_a::test_bad[1]": "failed",
        "tests.test_a::test_err": "error",
        "tests.test_a::test_skip": "skipped",
    }


def test_changed_lines_from_patch():
    patch = textwrap.dedent(
        """\
        diff --git a/x.py b/x.py
        --- a/x.py
        +++ b/x.py
        @@ -1,3 +1,4 @@
         a = 1
        -b = 2
        +b = 3
        +c = 4
         d = 5
        """
    )
    assert repo.changed_lines(patch) == {"x.py": {2, 3}}


def test_mutants_only_touch_added_lines_and_compile():
    source = "def f(x):\n    if x > 1:\n        return x + 1\n    return 0\n"
    muts = mutate.generate("m.py", source, {2, 3}, limit=50)
    assert muts, "expected mutants"
    ops = {m.operator for m in muts}
    assert {"cmp", "negate-if", "binop", "return-none"} <= ops
    for m in muts:
        compile(m.source, "m.py", "exec")
        assert m.line in {2, 3}
    assert all("return 0" in m.source for m in muts)  # line 4 untouched


def test_spread_is_deterministic_and_bounded():
    items = [mutate.Mutant("p", i, "op", "", str(i)) for i in range(40)]
    picked = mutate.spread(items, 8)
    assert len(picked) == 8
    assert picked == mutate.spread(items, 8)
    assert picked[0].line == 0


def test_diversity_flags_reworded_duplicates():
    specs = [
        {"id": "a", "axis": "x", "instruction": "Add aliases for group commands so ls runs list"},
        {"id": "b", "axis": "y", "instruction": "Add aliases for group commands so ls runs list quickly"},
    ]
    reports = {"a": {"touched_symbols": ["core.py:Group.get_command"]}, "b": {"touched_symbols": ["core.py:Group.get_command"]}}
    result = diversity.assess(specs, reports, 0.34, 0.55)
    assert not result["passed"]
    assert result["pairs"][0]["symbol_jaccard"] == 1.0


def test_replay_cache_round_trip(tmp_path):
    provider = llm.make_provider("handoff", "m", tmp_path / "cache", tmp_path / "pending")
    with pytest.raises(llm.PendingHandoff) as exc:
        provider.complete("propose", "prompt text")
    assert (tmp_path / "pending" / f"{exc.value.key}.md").exists()
    provider.store("propose", "prompt text", '{"ok": true}')
    replay = llm.make_provider("replay", "m", tmp_path / "cache", tmp_path / "pending")
    assert llm.extract_json(replay.complete("propose", "prompt text")) == {"ok": True}
    with pytest.raises(llm.CacheMiss):
        replay.complete("propose", "a different prompt")


def test_extract_json_tolerates_fences():
    assert llm.extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert llm.extract_json('Sure! {"a": [1, 2]} trailing') == {"a": [1, 2]}


def test_committed_cache_covers_every_generation_step():
    """The replay cache must be enough to regenerate every committed spec."""
    proposals = json.loads((ROOT / "output" / "proposals.json").read_text())
    keys = {proposals["provenance"]["key"]}
    for p in proposals["proposals"]:
        spec = json.loads((ROOT / "output" / "specs" / f"{p['id']}.json").read_text())
        keys |= {step["key"] for step in spec["provenance"]}
    for key in keys:
        assert (ROOT / "cache" / "llm" / f"{key}.json").exists(), key
