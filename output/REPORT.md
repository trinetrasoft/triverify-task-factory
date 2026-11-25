# TriVerify run report

- Target: `https://github.com/pallets/click` @ `8.5.1` (`cf19179e8e2fd54c601378cec9e0d21bb12b6fb1`)
- Generated: 2026-11-25T13:18:09Z · provider `replay` · model `claude-opus-5-5`
- Harbor: 0.25.0
- Baseline: 2459 tests collected, 2410 pass-to-pass (stable across 2 runs)

## Tasks

| Task | Axis | F2P | NOP (local) | ORACLE ×3 (local) | Mutation score | Harbor nop | Harbor oracle | All gates |
|---|---|---|---|---|---|---|---|---|
| `bytesize-param-type` | new parameter type | 13 | 0.0 | 1.0 / 1.0 / 1.0 | 8/8 = 1.0 | 0.0 | 1.0 | ✅ |
| `choice-unique-prefix-matching` | behaviour change to an existing type | 12 | 0.0 | 1.0 / 1.0 / 1.0 | 15/16 = 0.938 | 0.0 | 1.0 | ✅ |
| `group-command-aliases` | command dispatch and resolution | 13 | 0.0 | 1.0 / 1.0 / 1.0 | 14/16 = 0.875 | 0.0 | 1.0 | ✅ |
| `mutually-exclusive-options` | cross-parameter validation | 13 | 0.0 | 1.0 / 1.0 / 1.0 | 15/16 = 0.938 | 0.0 | 1.0 | ✅ |
| `option-help-sections` | help output rendering | 11 | 0.0 | 1.0 / 1.0 / 1.0 | 9/9 = 1.0 | 0.0 | 1.0 | ✅ |

## Variation

- Distinct axes: ✅; max code-footprint Jaccard 0.111 (≤ 0.34); max instruction cosine 0.248 (≤ 0.55) → ✅

| Pair | Footprint Jaccard | API Jaccard | Instruction cosine |
|---|---|---|---|
| bytesize-param-type ↔ choice-unique-prefix-matching | 0.0 | 0.333 | 0.104 |
| bytesize-param-type ↔ group-command-aliases | 0.0 | 0.0 | 0.1 |
| bytesize-param-type ↔ mutually-exclusive-options | 0.0 | 0.0 | 0.097 |
| bytesize-param-type ↔ option-help-sections | 0.0 | 0.0 | 0.108 |
| choice-unique-prefix-matching ↔ group-command-aliases | 0.0 | 0.0 | 0.078 |
| choice-unique-prefix-matching ↔ mutually-exclusive-options | 0.0 | 0.0 | 0.098 |
| choice-unique-prefix-matching ↔ option-help-sections | 0.0 | 0.0 | 0.054 |
| group-command-aliases ↔ mutually-exclusive-options | 0.111 | 0.25 | 0.248 |
| group-command-aliases ↔ option-help-sections | 0.0 | 0.25 | 0.164 |
| mutually-exclusive-options ↔ option-help-sections | 0.0 | 0.333 | 0.133 |

## Gate details

### bytesize-param-type

- ✅ `patch_applies`
- ✅ `no_leakage`
- ✅ `novel_upstream`
- ✅ `oracle_reward_1`
- ✅ `test_count_6_14`
- ✅ `nop_reward_0`
- ✅ `mutation_score`
- Generation trail: author

### choice-unique-prefix-matching

- ✅ `patch_applies`
- ✅ `no_leakage`
- ✅ `novel_upstream`
- ✅ `oracle_reward_1`
- ✅ `test_count_6_14`
- ✅ `nop_reward_0`
- ✅ `mutation_score`
- Surviving mutants (reviewed in docs/VALIDATION.md):
  - `src/click/types.py:484` iterate in reverse order
- Generation trail: author

### group-command-aliases

- ✅ `patch_applies`
- ✅ `no_leakage`
- ✅ `novel_upstream`
- ✅ `oracle_reward_1`
- ✅ `test_count_6_14`
- ✅ `nop_reward_0`
- ✅ `mutation_score`
- Surviving mutants (reviewed in docs/VALIDATION.md):
  - `src/click/core.py:1765` iterate in reverse order
  - `src/click/core.py:2181` And → Or
- Generation trail: author

### mutually-exclusive-options

- ✅ `patch_applies`
- ✅ `no_leakage`
- ✅ `novel_upstream`
- ✅ `oracle_reward_1`
- ✅ `test_count_6_14`
- ✅ `nop_reward_0`
- ✅ `mutation_score`
- Surviving mutants (reviewed in docs/VALIDATION.md):
  - `src/click/core.py:1439` iterate in reverse order
- Generation trail: author

### option-help-sections

- ✅ `patch_applies`
- ✅ `no_leakage`
- ✅ `novel_upstream`
- ✅ `oracle_reward_1`
- ✅ `test_count_6_14`
- ✅ `nop_reward_0`
- ✅ `mutation_score`
- Generation trail: author

