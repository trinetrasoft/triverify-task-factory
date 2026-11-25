# TriVerify Task Factory: technical explanation

Innodata AI Hackathon · Track 1 (Coding Task Factory) · Team **Trinetra Soft**

## 1. What the factory does

TriVerify turns a real repository into **Harbor 0.25 feature-development task packages**
for evaluating AI coding systems. It is a pipeline, not a collection of hand-made tasks:

```
configs/click.toml
      │
      ▼
 ① pin & analyse ──► ② propose ──► ③ author ──► ④ TRIPLE VERIFY ──► ⑤ package ──► ⑥ Harbor matrix ──► ⑦ report
   git clone at       5 features     instruction    nop / oracle×3 /     Harbor dir    harbor run nop      REPORT.md
   base commit,       on 5 distinct  + patch +      mutants + static     per task      & oracle in         report.html
   AST capability     variation      feature tests  gates  ─┐                          Docker              report.json
   map (no code run)  axes                                   └─► ③b repair (model) ◄─┘ on failure (≤2 rounds)
```

* **Target:** `pallets/click`, release `8.5.1`, base commit
  `cf19179e8e2fd54c601378cec9e0d21bb12b6fb1` (recorded in every `task.toml` under
  `[metadata] base_commit`). The full test suite passes at this commit.
* **Pipeline language:** Python 3.11+, standard library only. Harbor is the only
  optional dependency, used for the official validation matrix.
* **Generated tasks:** run in the repository's own language, dependencies and test runner
  (Python, `pip install -e .`, pytest).

## 2. Stages

| Stage | Module | What happens |
|---|---|---|
| Pin & analyse | `repo.py`, `analysis.py` | Clone, check out the exact base commit, verify the tag ↔ hash, and build a deterministic *capability map* of the public API by parsing source with `ast`. The target's code is never imported by the factory. |
| Propose | `generate.py`, `prompts/propose.md` | The model receives the capability map and the variation axes and must return N proposals, each on a **different axis**. Duplicate or unknown axes are rejected in code. |
| Author | `prompts/author.md` | For each proposal, the model receives the relevant source excerpts (AST-sliced by anchor class) and returns `instruction`, `solution_patch` (git diff) and `feature_tests`. Shape and syntax are checked before anything runs. |
| Triple verify | `validate.py`, `mutate.py`, `grading.py` | See §3. Failures become structured evidence for the repair stage. |
| Repair | `prompts/repair.md` | The model gets the package plus gate evidence (failing tests, regressions, surviving mutants) and must return a fixed package without weakening detection. Up to two rounds. |
| Package | `packager.py` | Writes the Harbor directory (instruction, `task.toml`, `environment/Dockerfile`, `solution/`, `tests/` with `fail_to_pass.json` / `pass_to_pass.json`). |
| Harbor matrix | `harbor_runner.py` | `harbor lint`, then `harbor run -a nop` (expect 0.0) and `harbor run -a oracle` (expect 1.0) per task, in Docker. |
| Report | `report.py`, `diversity.py` | JSON, Markdown and HTML reports with every gate, the mutation tables and the variation matrices. |

## 3. Triple verification ("Trinetra": three eyes)

Every task must pass all gates. Rewards are computed by **the same code** the Harbor
verifier runs: `triverify/grading.py` is copied verbatim into every package as
`tests/grade.py`.

1. **NOP gate:** the starting commit plus the new feature tests. Every feature test must
   fail on its own (tests reach the new API inside the test body, so one missing name
   cannot mask the others) and every pass-to-pass test must pass. Expected reward 0.0.
2. **ORACLE gate:** the reference patch applied, with the whole suite plus the feature tests
   run **three times**. Expected reward 1.0 every time, so the tests are not flaky.
3. **MUTANT gate:** mutation testing restricted to the lines the reference patch adds.
   Operators: comparison flips, boolean swap, condition negation, `not` removal, integer +1,
   boolean constant swap, arithmetic swap, `return x` → `return None`, `raise` → `pass`,
   call-statement deletion, `x = …` → `x = None`, and reversed `for` iteration. Each mutant
   is a whole-module `ast.unparse` rewrite that must compile. A control run checks that the
   unparsed, *unmutated* module still passes, so the method itself cannot cause false kills.
   Score must be ≥ 0.7.

Static gates:
- the patch applies to the starting commit;
- 6–14 feature tests per task;
- no solution code leaks into the instruction;
- none of the new public names exist upstream on `origin/main` (`git grep`), so the
  features are genuinely new.

**Pass-to-pass list:** the base suite is run twice, and only tests that pass in both runs
are kept. This removes environment-dependent tests up front.

**Reward formula** (from the guide), in `grading.compute_reward`:
- any pass-to-pass test not passing → 0.0;
- otherwise passed F2P / total F2P;
- a test missing from the report counts as failing.

## 4. Variation strategy

Five tasks from one repository, on five different axes, in different subsystems:

| Task | Axis | Subsystem |
|---|---|---|
| `bytesize-param-type` | new parameter type | `types.py`: new `ParamType` and package export |
| `choice-unique-prefix-matching` | behaviour change to an existing type | `types.py`: `Choice.convert` and a new message hook |
| `group-command-aliases` | command dispatch and resolution | `core.py`: `Group` registration, lookup, resolution and help |
| `mutually-exclusive-options` | cross-parameter validation | `core.py`: `Command.parse_args` with `ParameterSource` |
| `option-help-sections` | help output rendering | `core.py`: `Option` and `Command.format_options` |

`diversity.py` measures variation; it doesn't just claim it. It computes pairwise Jaccard
overlap of the functions and classes each reference patch modifies (taken from the patched
AST), overlap of the public API each test module exercises, and cosine similarity of the
instructions. The gate requires distinct axes, footprint overlap ≤ 0.34 and instruction
similarity ≤ 0.55. A reworded duplicate fails the gate, and the repository's unit tests
check this.

## 5. Reproducibility (judges' run)

```bash
git clone https://github.com/trinetrasoft/triverify-task-factory && cd triverify-task-factory
pip install -e . "harbor==0.25.*"
# recommended: run every gate inside the task image (needs Docker), same as CI
python -m triverify run --config configs/click.toml --provider replay --runner docker
# without Docker: a local interpreter with pytest
#   python -m venv /tmp/target && /tmp/target/bin/pip install pytest==8.4.1
#   TRIVERIFY_TARGET_PYTHON=/tmp/target/bin/python python -m triverify run --config configs/click.toml --provider replay
# or the official matrix for one package:
harbor run -p output/tasks/bytesize-param-type -a nop    -k 1 -o jobs --no-delete -y
harbor run -p output/tasks/bytesize-param-type -a oracle -k 1 -o jobs --no-delete -y
```

`--provider replay` answers every model call from `cache/llm/`, which is content-addressed
by `sha256(stage, model, prompt)`. That makes a judge's run bit-for-bit identical to ours
with no API key. `--provider anthropic|openai` regenerates live (keys from
`ANTHROPIC_API_KEY` / `OPENAI_API_KEY`) and records new cache entries. A unit test asserts
that the committed cache covers every generation step of every committed spec.

GitHub Actions (`.github/workflows/factory.yml`) runs this whole pipeline on every push,
including `harbor lint` and the Harbor nop/oracle matrix in Docker, and commits the
outputs back to `output/`.

## 6. Models and tools (declared as required by the rules)

| Use | Model / tool |
|---|---|
| Proposal, authoring and repair stages (sample outputs in this repo) | **Claude Opus 5.5** (Anthropic), answering the factory's hand-off prompts through a Claude Code agent session (`--provider handoff`). Every prompt/response pair is in `cache/llm/` with its stage, model and timestamp. |
| Live generation (optional) | Anthropic Messages API or OpenAI Chat Completions via `--provider anthropic|openai` |
| Task interface and validation | Harbor 0.25.x (`harbor lint`, `harbor run -a nop/oracle`), Docker |
| Test runner | pytest 8.4.1 (inside the task image and the local runner) |
| CI | GitHub Actions (ubuntu-latest, Docker) |

No other models are used. Mutation testing, diversity scoring, leakage and novelty checks
are deterministic code.

## 7. Design decisions and assumptions

* **Hand-off provider:** model calls are an explicit, replayable interface. That is what
  makes the factory auditable: a judge can see exactly what the model was asked and
  answered, and re-run without credentials.
* **Grader shared with Harbor:** a local emulator that scores differently from the
  official verifier would be worse than none. Sharing the file removes that risk.
* **Shallow, single-commit Docker checkout:** the task image fetches only the base commit
  and removes the remote, so an evaluated agent cannot read future history.
* **Whole-suite regression:** click's suite is fast, so every task guards all of its
  pass-to-pass tests (including `test_imports.py`, which forbids new stdlib imports; the
  `ByteSize` reference therefore uses exact integer arithmetic instead of `decimal`).
* **No info-dict changes:** existing `to_info_dict` snapshots are part of the regression
  suite, so the instructions explicitly keep them stable.
* **Out of scope by construction:** no network, credentials or security exploits in tasks
  (checked in the proposal prompt and by review).

## 8. Validation evidence

See [`VALIDATION.md`](VALIDATION.md) and [`../output/REPORT.md`](../output/REPORT.md)
(generated by CI), including surviving-mutant analysis and any manual fixes.
