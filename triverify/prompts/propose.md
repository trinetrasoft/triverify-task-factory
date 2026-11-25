You are the proposal stage of TriVerify, an automated factory that turns a real open-source
repository into feature-development tasks for evaluating AI coding systems.

# Repository
- Project: {repo_url}
- Pinned starting commit: {base_commit} (release {ref}); every existing test passes here.
- Language: {language}

# Public surface of the codebase at this commit
{capability_map}

# What to produce
Propose exactly {num_tasks} feature-development tasks for this repository. Each task must:
1. Add a new feature or change existing behaviour in a way a real maintainer would accept
   (no bug fixes, no refactors, no documentation-only changes).
2. Be achievable in a single focused change (roughly 30–200 changed lines of library code)
   and be fully specifiable in prose, so an engineer who only sees the instruction can
   implement it without seeing the reference solution.
3. Be verifiable with deterministic, offline unit tests written against the public API.
4. Not already exist in the project (on this commit or upstream).
5. Stay out of security-sensitive territory (no exploits, no network access, no credentials).

The {num_tasks} tasks must be *substantively different*: each must use a different variation
axis from this list and touch a different part of the codebase (different modules or
different classes). Renaming or rewording one idea is not variation.

Variation axes: {axes}

# Output
Return only one JSON object, no prose, with this shape:
{{
  "proposals": [
    {{
      "id": "kebab-case-slug",
      "axis": "<one axis from the list>",
      "title": "imperative one-line title",
      "summary": "2-4 sentences: the user-visible behaviour",
      "public_api": ["new public names or keyword arguments introduced"],
      "touches": ["repository paths expected to change"],
      "anchors": ["top-level classes or functions the change centres on"],
      "why_realistic": "why a maintainer would want this"
    }}
  ]
}}
