# Add a `click.ByteSize` parameter type for human-readable data sizes

Command-line tools often take sizes such as cache limits or upload quotas. Add a new
parameter type, `click.ByteSize`, that converts a human-readable size into an integer
number of bytes. It must be importable as `click.ByteSize` (and from `click.types`).

## API

```python
click.ByteSize(min: int | None = None, max: int | None = None)
```

It is a `click.ParamType` subclass whose `convert(value, param, ctx)` returns an `int`.

## Accepted values

- A string made of a non-negative number followed by an optional unit. Whitespace is
  allowed before and after the number and between the number and the unit.
- Units are case-insensitive:
  - no unit, or `B`: bytes;
  - `K`/`KB`, `M`/`MB`, `G`/`GB`, `T`/`TB`: powers of 1000;
  - `Ki`/`KiB`, `Mi`/`MiB`, `Gi`/`GiB`, `Ti`/`TiB`: powers of 1024.
- The number may have a fractional part written with a dot (`1.5MB`, `.5KB`, `2.MB`).
  The result must be computed exactly (no floating-point rounding) and must be a whole
  number of bytes.
- An `int` (but not a `bool`) is accepted as a size in bytes as-is.

Examples: `"512"` → 512, `"10KB"` → 10000, `"1.5 MiB"` → 1572864, `"2gib"` → 2147483648.

## Errors

Conversion failures must use the type's normal failure mechanism (`self.fail`, i.e. a
`click.BadParameter`), with exactly these messages, where `{value!r}` is the `repr` of the
original value:

- not parseable as a size (empty or blank strings, no digits, a sign, several dots,
  negative integers, booleans or other non-string values): `{value!r} is not a valid size.`
- a number followed by an unknown unit: `{value!r} has an unknown size unit {unit!r}.`
  where `unit` is the unit exactly as written by the user (for example `'XB'`).
- a fractional size that is not a whole number of bytes:
  `{value!r} is not a whole number of bytes.`
- below `min`: `{value!r} is smaller than the minimum size of {min} bytes.`
- above `max`: `{value!r} is larger than the maximum size of {max} bytes.`

Both bounds are inclusive and are checked after conversion, also for integer input.

## Integration

- The type's `name` is `"size"`, so the help page shows the metavar `SIZE`
  (for example `--limit SIZE`).
- `to_info_dict()` returns the usual `param_type` and `name` keys plus `min` and `max`.
- `repr(click.ByteSize())` is `"ByteSize"`.
- It must work as an option type with defaults given as strings, with `multiple=True`
  and with environment variables (whitespace-separated lists), like other types.

Importing `click` must not import any additional standard-library modules beyond the ones
click already uses. All existing behaviour and the existing test suite must keep working.
