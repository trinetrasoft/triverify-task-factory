"""Write Harbor (v0.25.x) task packages.

Layout of every generated task::

    <task-id>/
      instruction.md            # the only file the evaluated AI system sees
      task.toml                 # schema 1.4, base_commit recorded in [metadata]
      environment/Dockerfile    # target repo fetched at the exact base commit
      solution/solve.sh         # oracle: applies the reference patch
      solution/solution.patch
      tests/test.sh             # verifier entry point (shared environment)
      tests/grade.py            # == triverify/grading.py (same reward code)
      tests/feature/<module>.py # the new feature tests
      tests/fail_to_pass.json   # SWE-bench style test lists
      tests/pass_to_pass.json
"""

from __future__ import annotations

import json
import shutil
from importlib import resources
from pathlib import Path

from .config import Config
from .validate import feature_module

GENERATOR = "triverify 0.1.0"
AGENT_PATCH = "/tmp/triverify/agent.patch"
# Snapshot everything the agent changed in /app except the test suite.
COLLECT_CMD = (
    "mkdir -p /tmp/triverify && cd /app && git add -A && "
    "git diff --cached --binary -- . ':(exclude)tests' > " + AGENT_PATCH
)


def _toml_str(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _toml_list(values: list[str]) -> str:
    return "[" + ", ".join(_toml_str(v) for v in values) + "]"


def task_toml(cfg: Config, spec: dict, report: dict) -> str:
    t, f = cfg.target, cfg.factory
    name = f"{f.org}/{t.name}-{spec['id']}"
    gates = report.get("gates", {})
    mutation = report.get("mutation", {})
    return f"""schema_version = "1.4"
# The verifier runs in a fresh copy of the environment and only receives the
# agent's changes as a patch that excludes tests/ (tamper-proof regression suite).
artifacts = [{_toml_str(AGENT_PATCH)}]

[task]
name = {_toml_str(name)}
version = "1.0.0"
description = {_toml_str(spec['title'])}
authors = [{{ name = {_toml_str(f.author_name)}, email = {_toml_str(f.author_email)} }}]
keywords = {_toml_list([t.name, t.language, 'feature-development', spec['axis'], *spec.get('tags', [])])}

[metadata]
repo = {_toml_str(t.url.removeprefix('https://github.com/'))}
repo_url = {_toml_str(t.url)}
base_ref = {_toml_str(t.ref)}
base_commit = {_toml_str(t.base_commit)}
license = {_toml_str(t.license)}
language = {_toml_str(t.language)}
test_runner = "pytest"
category = "feature-development"
variation_axis = {_toml_str(spec['axis'])}
difficulty = {_toml_str(spec.get('difficulty', 'medium'))}
public_api = {_toml_list(spec.get('public_api', []))}
generator = {_toml_str(GENERATOR)}
generation_model = {_toml_str(cfg.generation.model)}
fail_to_pass_count = {len(report.get('fail_to_pass', []))}
mutation_score = {mutation.get('score') if mutation.get('score') is not None else 0.0}
triverify_gates_passed = {str(all(gates.values()) if gates else False).lower()}

[verifier]
timeout_sec = 1200.0
environment_mode = "separate"

[[verifier.collect]]
command = {_toml_str(COLLECT_CMD)}
timeout_sec = 120.0

[agent]
timeout_sec = 3600.0

[environment]
build_timeout_sec = 1200.0
cpus = 2
memory_mb = 4096
storage_mb = 10240
"""


def dockerfile(cfg: Config) -> str:
    t = cfg.target
    return f"""FROM {t.docker_base}

ENV PYTHONDONTWRITEBYTECODE=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
RUN apt-get update \\
    && apt-get install -y --no-install-recommends git ca-certificates \\
    && rm -rf /var/lib/apt/lists/*

# The repository at the exact starting commit only: no upstream history, no refs
# that could leak a future implementation.
WORKDIR /app
RUN git init -q . \\
    && git remote add origin {t.url} \\
    && git fetch -q --depth 1 origin {t.base_commit} \\
    && git checkout -q --detach FETCH_HEAD \\
    && test "$(git rev-parse HEAD)" = "{t.base_commit}" \\
    && git remote remove origin \\
    && git config --global user.email "agent@example.com" \\
    && git config --global user.name "agent"

RUN {t.install} \\
    && git ls-files --others --exclude-standard >> .git/info/exclude \\
    && test -z "$(git status --porcelain)"
"""


SOLVE_SH = """#!/bin/bash
# Oracle: apply the reference implementation to the starting commit.
set -euo pipefail
cd /app
git apply --whitespace=nowarn /solution/solution.patch
echo "reference solution applied"
"""

TEST_SH = """#!/bin/bash
# TriVerify verifier (separate container, clean checkout of the base commit):
# apply the agent's changes (collected without tests/), add the feature tests,
# run the whole suite once and score it with the shared reward formula.
cd /app
mkdir -p /logs/verifier
if [ -s {agent_patch} ]; then
  if git apply --whitespace=nowarn {agent_patch}; then
    echo "agent patch applied ($(wc -l < {agent_patch}) lines)" > /logs/verifier/agent-patch.txt
  else
    echo "agent patch did not apply" > /logs/verifier/agent-patch.txt
  fi
else
  echo "no agent changes" > /logs/verifier/agent-patch.txt
fi
cp /tests/feature/*.py /app/{tests_dir}/
python /tests/grade.py --repo /app --tests-dir /tests --out /logs/verifier --target {tests_dir}
# grade.py always writes /logs/verifier/reward.txt; never fail the script itself.
exit 0
"""


def write(cfg: Config, spec: dict, report: dict, p2p: list[str], out_dir: Path) -> Path:
    task_dir = out_dir / spec["id"]
    if task_dir.exists():
        shutil.rmtree(task_dir)
    (task_dir / "environment").mkdir(parents=True)
    (task_dir / "solution").mkdir()
    (task_dir / "tests" / "feature").mkdir(parents=True)

    (task_dir / "instruction.md").write_text(spec["instruction"].rstrip() + "\n")
    (task_dir / "task.toml").write_text(task_toml(cfg, spec, report))
    (task_dir / "environment" / "Dockerfile").write_text(dockerfile(cfg))

    (task_dir / "solution" / "solution.patch").write_text(spec["solution_patch"].rstrip("\n") + "\n")
    solve = task_dir / "solution" / "solve.sh"
    solve.write_text(SOLVE_SH)
    solve.chmod(0o755)

    module = feature_module(cfg, spec["id"])
    (task_dir / "tests" / "feature" / f"{module}.py").write_text(spec["feature_tests"])
    test_sh = task_dir / "tests" / "test.sh"
    test_sh.write_text(TEST_SH.format(tests_dir=cfg.target.tests_dir, agent_patch=AGENT_PATCH))
    test_sh.chmod(0o755)
    grade_src = resources.files("triverify").joinpath("grading.py").read_text()
    (task_dir / "tests" / "grade.py").write_text(grade_src)
    (task_dir / "tests" / "fail_to_pass.json").write_text(json.dumps(report["fail_to_pass"], indent=1))
    (task_dir / "tests" / "pass_to_pass.json").write_text(json.dumps(p2p, indent=1))
    return task_dir
