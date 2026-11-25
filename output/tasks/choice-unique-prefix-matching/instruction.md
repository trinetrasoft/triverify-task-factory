# Let `click.Choice` accept unambiguous prefixes of its choices

Many tools accept abbreviations of fixed choices (`--format y` for `yaml`). Add opt-in
prefix matching to `click.Choice`.

## API

```python
click.Choice(choices, case_sensitive: bool = True, allow_prefix: bool = False)
```

Store the flag on the instance as `allow_prefix`. With `allow_prefix=False` (the default)
behaviour is exactly as today.

## Matching rules when `allow_prefix=True`

Values and choices are normalised exactly as `Choice` already does
(`normalize_choice`: enum members by name, the context's `token_normalize_func`, and
case folding when `case_sensitive=False`). Then:

1. An exact match on a normalised choice always wins, even if it is also a prefix of
   other choices (with choices `dev` and `development`, `dev` selects `dev`).
2. Otherwise, if the normalised value is a prefix of exactly one normalised choice, that
   choice is returned (the original choice object, e.g. the enum member).
3. If it is a prefix of several choices, conversion fails with the message
   `{value!r} is ambiguous; it could be one of {choices}.` where `{choices}` lists the
   matching *normalised* choices, each in `repr` form, separated by `", "`, in the order
   the choices were given. Example: `'de' is ambiguous; it could be one of 'deploy', 'debug'.`
4. An empty value is never treated as a prefix.
5. Anything else fails with the existing invalid-choice message, unchanged.

Failures use the type's normal failure mechanism (`click.BadParameter`), so on the command
line they appear as the usual `Invalid value for '--opt': …` usage error.

Expose the ambiguity message through a new overridable method, mirroring
`get_invalid_choice_message`:

```python
Choice.get_ambiguous_choice_message(self, value, candidates, ctx) -> str
```

where `candidates` is the list of matching normalised choice strings.

## Unchanged

`to_info_dict()`, metavars, the missing-value message, shell completion and every existing
behaviour of `Choice` must stay the same, and the existing test suite must keep passing.
