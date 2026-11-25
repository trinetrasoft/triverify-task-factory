# Validation evidence

Source of truth: [`output/report.json`](../output/report.json), [`output/REPORT.md`](../output/REPORT.md),
[`output/logs/factory-run.log`](../output/logs/factory-run.log) and `output/harbor/*.json`.
GitHub Actions wrote all of them in
[run 45620287315](https://github.com/trinetrasoft/triverify-task-factory/actions/runs/45620287315)
(commit `2d75bc9`). The `factory` job took 11 min 10 s end to end on `ubuntu-latest`.

## 1. Environment

* Every gate ran **inside the task image** (`triverify/click-env:cf19179e8e2f`, built from the
  same `environment/Dockerfile` the Harbor package ships) with `--network none`.
* Baseline: 2459 tests collected at `cf19179`, of which **2410 passed in both runs**. Those
  2410 form the pass-to-pass list. The other 49 are environment-dependent in the slim image
  (for example the `echo_via_pager` tests, which need `less`) or are skipped/xfail upstream.

## 2. Harbor matrix (official interface, Harbor 0.25.0)

| Task | `harbor lint` | nop reward (expect 0.0) | oracle reward (expect 1.0) |
|---|---|---|---|
| bytesize-param-type | 0 findings | 0.0 ✅ | 1.0 ✅ |
| choice-unique-prefix-matching | 0 findings | 0.0 ✅ | 1.0 ✅ |
| group-command-aliases | 0 findings | 0.0 ✅ | 1.0 ✅ |
| mutually-exclusive-options | 0 findings | 0.0 ✅ | 1.0 ✅ |
| option-help-sections | 0 findings | 0.0 ✅ | 1.0 ✅ |

The verifier runs in **separate mode**: a collect hook exports the agent's diff (excluding
`tests/`) from the agent container, and the verifier container applies it to a clean
checkout before it adds the hidden feature tests. An agent cannot edit or delete the
grading tests.

## 3. Factory gates

| Task | F2P tests | NOP | ORACLE ×3 | Mutation score | Generation rounds |
|---|---|---|---|---|---|
| bytesize-param-type | 13 | 0.0 | 1.0 / 1.0 / 1.0 | 8/8 = 1.00 | 0 repairs |
| choice-unique-prefix-matching | 12 | 0.0 | 1.0 / 1.0 / 1.0 | 15/16 = 0.94 | 0 repairs |
| group-command-aliases | 13 | 0.0 | 1.0 / 1.0 / 1.0 | 14/16 = 0.88 | 0 repairs |
| mutually-exclusive-options | 13 | 0.0 | 1.0 / 1.0 / 1.0 | 15/16 = 0.94 | 0 repairs |
| option-help-sections | 11 | 0.0 | 1.0 / 1.0 / 1.0 | 9/9 = 1.00 | 0 repairs |

All static gates passed for all five tasks: the patch applies, 6–14 tests, no leakage, and
the feature is not upstream. The unparse control run passed for every task, so no kill
comes from the mutation method itself.

Variation: 5 distinct axes, maximum code-footprint Jaccard **0.111** (limit 0.34), maximum
instruction cosine **0.248** (limit 0.55).

## 4. Surviving mutants: manual review

Each of the 4 survivors was reviewed by hand against the patched source.

| Task | Location | Mutation | Verdict |
|---|---|---|---|
| choice-unique-prefix-matching | `types.py:484` | iterate `normalized_mapping` in reverse during exact matching | **Equivalent.** Exact matching returns the single original whose normalized form equals the input. Order matters only when two distinct choices normalize to the same value (for example `a` and `A` with `case_sensitive=False`). That is a degenerate configuration the task does not specify. |
| group-command-aliases | `core.py:1765` | register constructor-supplied commands' aliases in reverse | **Equivalent for valid input.** Registration order only changes *which* of two conflicting registrations raises first. Either way a `ValueError` is raised, and the tests assert that it is raised. |
| group-command-aliases | `core.py:2181` | `cmd is not None and cmd_name not in self.commands` → `or` | **Equivalent.** If `cmd` is `None` the function returns `None` for the name anyway. If the name is a registered command it is never also an alias (registration forbids it), so the `.get(name, name)` lookup returns the name unchanged. |
| mutually-exclusive-options | `core.py:1439` | check exclusive groups in reverse order | **Semantically weak.** It differs only when *two* groups are violated in one invocation, where it changes which group's message is reported. The instruction does not define a priority between groups, so asserting one would over-specify the task. We kept it as a documented survivor. |

Conclusion: no survivor shows a behaviour that the instruction requires and the tests
miss.

## 5. Manual fixes during development

These were applied to the factory itself, not hand-patched into task outputs:

1. The capability map listed overloaded methods twice → de-duplicated, and an `anchors`
   field was added to the proposal schema.
2. Leakage check false positive on parameter-declaration lines such as
   `case_sensitive: bool = True,` → those lines are exempted.
3. `option-help-sections` produced only 1 mutant → added the statement-deletion,
   assign-`None` and reverse-iteration operators.
4. Feature-test ids are matched by prefix (`is_feature`), not by exact module name.
5. `bytesize-param-type`: click's `tests/test_imports.py` forbids new stdlib imports such
   as `decimal`, so the reference uses exact integer arithmetic.
6. CI run 1: Harbor oracle scored 0.0 because 24 `echo_via_pager` tests pass on the host
   but fail in `python:3.12-slim`. Fixed by **environment parity**: every gate, including
   the baseline, now runs inside the task image (`--runner docker --rebaseline`).
7. CI run 1: `harbor lint` reported a shared-verifier finding → switched to a separate
   verifier with a collect hook, so the grading tests cannot be tampered with.

After fixes 6 and 7, CI run 2 passed every gate on the first generation round.
