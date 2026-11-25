You are the authoring stage of TriVerify. Turn one approved proposal into a complete,
self-verifying task package for the repository below.

# Repository
- Project: {repo_url} at commit {base_commit} (release {ref})
- Language: {language}; tests run with pytest from the repository root.
- Existing test modules (read-only, they are the regression suite): {test_modules}

# Proposal
```json
{proposal}
```

# Relevant source at the starting commit
{source_excerpts}

# Requirements for the package
**instruction** (Markdown, the only file the evaluated AI system will see)
- Describe the required behaviour completely: public API names and signatures, defaults,
  edge cases, exact error/exit behaviour and any user-visible text that tests assert on.
- Do not mention the tests, the reference solution, file names of tests, or hints that
  only make sense with the solution in hand. Do not paste implementation code.
- State that existing behaviour and the existing test suite must keep working.

**solution_patch** (unified diff against the starting commit, `a/` and `b/` prefixes)
- A clean, idiomatic implementation that a maintainer would merge, including docstrings.
- Only library code; do not modify existing tests.

**feature_tests** (one pytest module, standard library + pytest + the project only)
- Between 6 and 14 tests that pass with the solution and fail without it.
- Every test must fail *on its own* on the starting commit: reach new API through the
  package namespace inside the test body (for example `click.NewThing`) rather than at
  import time, so one missing name does not hide the other tests.
- Cover the happy path, defaults, boundaries, error messages, and interaction with
  existing features, so that plausible but incorrect implementations are caught.
- Deterministic: no network, no sleeps, no reliance on terminal size or locale.

Return only one JSON object, no prose:
{{
  "id": "{task_id}",
  "title": "…",
  "axis": "…",
  "difficulty": "easy|medium|hard",
  "tags": ["…"],
  "public_api": ["…"],
  "instruction": "…markdown…",
  "solution_patch": "diff --git a/… b/…\n…",
  "feature_tests": "import click\n…"
}}
