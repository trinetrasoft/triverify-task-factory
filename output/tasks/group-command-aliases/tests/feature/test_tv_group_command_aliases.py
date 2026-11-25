import pytest

import click
from click.testing import CliRunner


def _make_cli():
    @click.group()
    def cli():
        pass

    @cli.command("list", aliases=["ls"])
    def list_cmd():
        """List things."""
        click.echo(f"list as {click.get_current_context().info_name}")

    @cli.command("remove", aliases=("rm", "del"))
    def remove_cmd():
        """Remove things."""
        click.echo("removed")

    @cli.command()
    def status():
        """Show status."""
        click.echo("ok")

    return cli


def test_command_stores_aliases():
    cmd = click.Command("remove", aliases=["rm", "del"])
    assert cmd.aliases == ("rm", "del")
    assert click.Command("plain", aliases=None).aliases == ()


def test_invoke_through_alias():
    runner = CliRunner()
    result = runner.invoke(_make_cli(), ["ls"])
    assert result.exit_code == 0, result.output
    assert result.output == "list as list\n"


def test_every_alias_and_canonical_name_work():
    cli = _make_cli()
    runner = CliRunner()
    for name in ["remove", "rm", "del"]:
        result = runner.invoke(cli, [name])
        assert result.output == "removed\n", name


def test_invoked_subcommand_is_canonical_name():
    seen = []

    @click.group(invoke_without_command=True)
    @click.pass_context
    def cli(ctx):
        seen.append(ctx.invoked_subcommand)

    @cli.command("checkout", aliases=["co"])
    def checkout():
        pass

    result = CliRunner().invoke(cli, ["co"])
    assert result.exit_code == 0, result.output
    assert seen == ["checkout"]


def test_get_command_and_list_commands():
    cli = _make_cli()
    ctx = click.Context(cli)
    assert cli.get_command(ctx, "ls") is cli.commands["list"]
    assert cli.get_command(ctx, "del") is cli.commands["remove"]
    assert cli.get_command(ctx, "nope") is None
    assert cli.list_commands(ctx) == ["list", "remove", "status"]


def test_help_lists_aliases_next_to_names():
    result = CliRunner().invoke(_make_cli(), ["--help"], terminal_width=80)
    lines = result.output.splitlines()
    assert any(line.strip().startswith("list (ls)") for line in lines)
    assert any(line.strip().startswith("remove (rm, del)") for line in lines)
    status_line = next(line for line in lines if "Show status." in line)
    assert status_line.split()[0] == "status"
    assert "(" not in status_line


def test_alias_cannot_shadow_existing_command():
    cli = click.Group("cli", commands=[click.Command("ls")])
    with pytest.raises(ValueError, match="'ls' of command 'list' is already a command"):
        cli.add_command(click.Command("list", aliases=["ls"]))


def test_alias_cannot_be_reused():
    cli = click.Group("cli")
    cli.add_command(click.Command("list", aliases=["l"]))
    with pytest.raises(ValueError, match="already an alias of command 'list'"):
        cli.add_command(click.Command("load", aliases=["l"]))


def test_command_name_cannot_take_an_alias():
    cli = click.Group("cli")
    cli.add_command(click.Command("list", aliases=["ls"]))
    with pytest.raises(ValueError, match="'ls' is already an alias of command 'list'"):
        cli.add_command(click.Command("ls"))


def test_replacing_a_command_drops_its_old_aliases():
    cli = click.Group("cli")
    cli.add_command(click.Command("list", aliases=["ls"]))
    cli.add_command(click.Command("list"))
    ctx = click.Context(cli)
    assert cli.get_command(ctx, "ls") is None
    cli.add_command(click.Command("ls"))
    assert cli.get_command(ctx, "ls").name == "ls"


def test_aliases_from_group_constructor():
    status = click.Command(
        "status", aliases=["st"], callback=lambda: click.echo("status ok")
    )
    cli = click.Group("cli", commands=[status])
    assert CliRunner().invoke(cli, ["st"]).output == "status ok\n"
    with pytest.raises(ValueError):
        click.Group("cli", commands=[status, click.Command("st")])


def test_aliases_in_chain_mode():
    @click.group(chain=True)
    def cli():
        pass

    @cli.command("build", aliases=["b"])
    def build():
        click.echo("build")

    @cli.command("test", aliases=["t"])
    def test_():
        click.echo("test")

    result = CliRunner().invoke(cli, ["b", "t", "build"])
    assert result.exit_code == 0, result.output
    assert result.output == "build\ntest\nbuild\n"


def test_unknown_command_error_is_unchanged():
    result = CliRunner().invoke(_make_cli(), ["nope"])
    assert result.exit_code == 2
    assert "No such command 'nope'." in result.output
