You are the repair stage of TriVerify. A task package you authored failed automated
validation. Fix it and return the full corrected package.

# Repository
{repo_url} at commit {base_commit} (release {ref})

# Current package
```json
{package}
```

# Validation failures (gate → evidence)
{failures}

# Rules
- Keep the task id, axis and the user-visible feature the same.
- If the reference solution is wrong, fix the patch. If a feature test is wrong or
  flaky, fix the test, but never weaken a test until it no longer detects the missing
  feature. Surviving mutants mean the tests are too weak: add assertions that kill them.
- If the instruction under-specifies something a test asserts on, make the instruction
  precise rather than deleting the assertion.

Return only one JSON object with the same shape as the current package.
