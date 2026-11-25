<p align="center"><img src="docs/trinetra-logo.png" alt="Trinetra Soft" height="90"></p>

<h1 align="center">TriVerify Task Factory</h1>
<p align="center"><b>A pipeline that turns a real codebase into triple-verified Harbor tasks for benchmarking AI coding agents.</b><br>
Innodata AI Hackathon · Track 1: Coding Task Factory · Team <b>Trinetra Soft</b></p>

<p align="center">
<a href="https://github.com/trinetrasoft/triverify-task-factory/actions/workflows/factory.yml"><img src="https://github.com/trinetrasoft/triverify-task-factory/actions/workflows/factory.yml/badge.svg" alt="factory"></a>
</p>

---

## Results (target `pallets/click` 8.5.1 @ `cf19179e8e2f`)

| Task | Variation axis | F2P tests | Harbor nop | Harbor oracle | Mutation score |
|---|---|---|---|---|---|
| [`bytesize-param-type`](output/tasks/bytesize-param-type) | new parameter type | 13 | 0.0 ✅ | 1.0 ✅ | 1.00 |
| [`choice-unique-prefix-matching`](output/tasks/choice-unique-prefix-matching) | behaviour change to an existing type | 12 | 0.0 ✅ | 1.0 ✅ | 0.94 |
| [`group-command-aliases`](output/tasks/group-command-aliases) | command dispatch and resolution | 13 | 0.0 ✅ | 1.0 ✅ | 0.88 |
| [`mutually-exclusive-options`](output/tasks/mutually-exclusive-options) | cross-parameter validation | 13 | 0.0 ✅ | 1.0 ✅ | 0.94 |
| [`option-help-sections`](output/tasks/option-help-sections) | help output rendering | 11 | 0.0 ✅ | 1.0 ✅ | 1.00 |

* `harbor lint`: 0 findings on every package. 2410 pass-to-pass tests are guarded in every task.
* Variation: maximum code-footprint overlap 0.11 and maximum instruction similarity 0.25.
* Every number above was produced by GitHub Actions and committed back to [`output/`](output). See [`output/REPORT.md`](output/REPORT.md) and [`docs/VALIDATION.md`](docs/VALIDATION.md).

## Why it is different: three eyes on every task

The name comes from *Trinetra*, "three eyes". A task ships only if three independent checks agree:

1. **NOP eye:** the untouched repo plus the hidden tests must score **0.0**. Every feature test fails, and all 2410 regression tests still pass.
2. **ORACLE eye:** the reference patch must score **1.0 three times in a row**, so there are no flaky tests.
3. **MUTANT eye:** we mutate *only the lines the reference patch adds* (12 AST operators) and require ≥ 70 % of mutants to be killed. This proves the tests check the feature's behaviour, not merely that it exists. A control run guards against false kills.

On top of these come static gates: the patch applies, 6–14 tests, no solution leakage into the instruction, and novelty against upstream `main` (`git grep`). A diversity gate also scores code-footprint and wording overlap between tasks.

Failing tasks go back to the model with structured evidence (failing tests, regressions, surviving mutants) for up to 2 repair rounds.

```
config ─► ① pin & AST map ─► ② propose (distinct axes) ─► ③ author ─► ④ NOP · ORACLE×3 · MUTANT + static gates
                                                              ▲                    │ fail
                                                              └──── ③b repair ◄────┘
                                                     pass ─► ⑤ Harbor package ─► ⑥ harbor lint + nop/oracle ─► ⑦ report
```

Engineering choices that make the results trustworthy:

* **One grader:** `triverify/grading.py` is copied verbatim into every package as `tests/grade.py`, so the local gates and Harbor score with identical code.
* **Environment parity:** all gates run inside the task's own Docker image with no network.
* **Tamper-proof verification:** a separate verifier collects the agent's diff (excluding `tests/`) and applies it to a clean checkout.
* **Leak-proof checkout:** the image fetches only the base commit and removes the remote, so an agent cannot read future history.
* **Replayable model calls:** every model prompt and answer is content-addressed in `cache/llm/`, so a judge's run is identical to ours with no API key.

## Quick start

```bash
git clone https://github.com/trinetrasoft/triverify-task-factory && cd triverify-task-factory
pip install -e . "harbor==0.25.*"
python -m triverify run --config configs/click.toml --provider replay --runner docker
# live generation instead of replay:
#   ANTHROPIC_API_KEY=... python -m triverify run --config configs/click.toml --provider anthropic --force
# the official matrix for one package:
harbor run -p output/tasks/bytesize-param-type -a oracle -k 1 -o jobs --no-delete -y
```

To point the factory at another Python repository, write a new `configs/<repo>.toml` (URL, tag, commit, source dirs, install command). The pipeline itself is repository-agnostic.

## Repository map

| Path | Contents |
|---|---|
| `triverify/` | the pipeline: `repo`, `analysis`, `generate`, `validate`, `mutate`, `diversity`, `packager`, `harbor_runner`, `report`, `cli` |
| `triverify/prompts/` | propose / author / repair prompts |
| `configs/click.toml` | target and factory configuration |
| `cache/llm/` | recorded model calls (stage, model, prompt, response) |
| `output/tasks/` | **the 5 Harbor task packages** |
| `output/` | report.json / REPORT.md / report.html, per-task validation, Harbor results, run log |
| `docs/TECHNICAL.md` | technical explanation |
| `docs/VALIDATION.md` | validation evidence, surviving-mutant review, manual fixes |
| `docs/media/` | submission deck (PDF) and demo video |
| `.github/workflows/factory.yml` | CI: unit tests, then the whole factory and Harbor matrix in Docker |

## Models and tools

Claude Opus 5.5 (Anthropic) generated the proposals, instructions, patches and tests through the factory's hand-off prompts. Every call is recorded in `cache/llm/`. Live runs can use the Anthropic or OpenAI APIs. Harbor 0.25, Docker, pytest 8.4.1 and GitHub Actions do the validation. Mutation, diversity, leakage and novelty checks are deterministic code.

## Team Trinetra Soft

Surya Santhosh (team leader) · Yogi Raja · Murthy · [trinetrasoft.com](https://trinetrasoft.com)

License: Apache-2.0. Generated tasks build on [pallets/click](https://github.com/pallets/click) (BSD-3-Clause).
