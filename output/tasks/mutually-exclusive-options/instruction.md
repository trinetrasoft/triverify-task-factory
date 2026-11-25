# Declare mutually exclusive parameters on a command

Let a command declare groups of parameters of which the user may provide at most one,
such as `--json`, `--yaml` and `--csv`.

## API

- `click.Command(..., mutually_exclusive=None)`: a sequence of groups, each a sequence of
  parameter *names* (the Python names, e.g. `"as_json"` for `--json/as_json`). It is
  stored on `Command.mutually_exclusive` as a tuple of tuples (empty tuple by default).
  Groups also accept it, and so do the decorators, e.g.
  `@click.command(mutually_exclusive=[("as_json", "as_yaml")])`.
- At construction, every group must contain at least two *different* names, otherwise
  raise `ValueError` with a message containing
  `at least two different parameter names`.
- A new public method `Command.check_mutually_exclusive(ctx)` performs the check
  described below. It is called while parsing, after every parameter has been processed
  and before the command callback (or a group's subcommand) runs. It is skipped when the
  context uses `resilient_parsing`.

## Rules

- A parameter counts as *provided* when its value came from the command line, an
  environment variable or a prompt (see `ctx.get_parameter_source`). Values from the
  parameter's default or from `default_map` never count.
- A flag's off-switch (`--no-color` for `--color/--no-color`) counts as providing it.
  Arguments can be part of a group too.
- If two or more parameters of one group are provided, fail with a `click.UsageError`
  (exit code 2) whose message is `Parameters {names} cannot be used together.` where
  `{names}` lists the provided parameters in the order they appear in the group, each
  named by its `get_error_hint(ctx)` (e.g. `'--json'`, or `'[SOURCE]'` for an optional
  argument), joined with `", "` except that the last two are joined with `" and "`:
  `Parameters '--json', '--yaml' and '--csv' cannot be used together.`
- Groups are checked independently.
- If a group names a parameter that the command does not have, raise `TypeError`
  whose message includes the unknown name in quotes (e.g. `'missing'`).

`Command.to_info_dict()` must not change. All existing behaviour and the existing test
suite must keep working.
