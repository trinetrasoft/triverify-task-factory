# Group options under custom headings on the help page

Large CLIs organise their options into blocks such as "Network" or "Output". Add a way to
choose the help-page heading an option is listed under.

## API

- `click.Option(..., help_section=None)`: a new keyword argument (also accepted by the
  `@click.option` decorator) stored on `Option.help_section`. `None` means the option is
  listed under the usual `Options` heading.

## Help rendering (`Command.format_options`)

1. Options without a section, including the automatic `--help` option, are listed under
   `Options` exactly as today.
2. Options with the same `help_section` are listed together under a heading with that
   exact text, in the order the options are declared.
3. Section headings come after the `Options` section, ordered by the first option that
   uses each section (not alphabetically).
4. Hidden options are not shown, and a heading is only printed if at least one visible
   option belongs to it. If every visible option has a section, no `Options` heading is
   printed.
5. Each option's help record (names, metavar, help text, `[default: …]` etc.) is rendered
   exactly as before; only its placement changes.
6. Commands that don't use `help_section` (or pass `help_section=None` explicitly) produce
   byte-for-byte the same help page as before. The `Positional arguments` section and,
   for groups, the `Commands` section keep their positions (sections appear before
   `Commands`).

`Option.to_info_dict()` must not change. All existing behaviour and the existing test
suite must keep working.
