# Support aliases for subcommands of a `click.Group`

Add short alternative names for subcommands, for example `ls` for `list`.

## API

- `click.Command(..., aliases=None)`: a new keyword argument accepting a sequence of
  strings. It is stored as a tuple on `Command.aliases` (an empty tuple when not given).
  Because the `@command` / `@group.command()` decorators forward extra keyword arguments,
  `@cli.command("list", aliases=["ls"])` must work, and so must groups created with
  `aliases=`.

## Group behaviour

1. Registration: aliases are registered when a command is added with
   `Group.add_command` and also for commands passed to `Group(commands=...)`
   (as a mapping or a sequence).
2. Resolution: `Group.get_command(ctx, name)` returns the command for a registered alias.
   Invoking a group with an alias runs that command exactly as its canonical name would,
   including in `chain=True` groups.
3. The canonical name is reported everywhere: `ctx.invoked_subcommand` of the group and
   `info_name` of the subcommand's context are the name the command is registered under,
   not the alias.
4. `list_commands` does not include aliases. Unknown names still produce the existing
   `No such command '…'.` error.
5. Help: in the group's `Commands` section, a command with aliases is listed as
   `name (alias1, alias2)` (aliases in declaration order, separated by `", "`).
   Commands without aliases are listed exactly as before.
6. Conflicts raise `ValueError` at registration time:
   - an alias equal to another registered command's name:
     `Alias {alias!r} of command {name!r} is already a command name.`
   - an alias already used by another command:
     `Alias {alias!r} of command {name!r} is already an alias of command {other!r}.`
   - registering a command whose name is an existing alias of a different command:
     `Command name {name!r} is already an alias of command {other!r}.`
7. Re-registering a command under the same name replaces it, and the aliases of the
   replaced command are dropped (only the new command's aliases remain registered).

`Command.to_info_dict()` must not change. All existing behaviour and the existing test
suite must keep working.
