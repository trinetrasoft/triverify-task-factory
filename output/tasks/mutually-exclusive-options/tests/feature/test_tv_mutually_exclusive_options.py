import pytest

import click
from click.testing import CliRunner


def _format_cli(calls=None):
    @click.command(mutually_exclusive=[["as_json", "as_yaml", "as_csv"]])
    @click.option("--json", "as_json", is_flag=True)
    @click.option("--yaml", "as_yaml", is_flag=True, envvar="TV_YAML")
    @click.option("--csv", "as_csv", is_flag=True)
    @click.option("--level", default=3)
    def cli(as_json, as_yaml, as_csv, level):
        if calls is not None:
            calls.append(True)
        click.echo(f"json={as_json} yaml={as_yaml} csv={as_csv} level={level}")

    return cli


def test_attribute_is_normalized():
    cmd = click.Command("c", mutually_exclusive=[["a", "b"], ("c", "d", "e")])
    assert cmd.mutually_exclusive == (("a", "b"), ("c", "d", "e"))
    assert click.Command("c", mutually_exclusive=None).mutually_exclusive == ()


def test_single_parameter_is_allowed():
    result = CliRunner().invoke(_format_cli(), ["--yaml", "--level", "5"])
    assert result.exit_code == 0, result.output
    assert result.output == "json=False yaml=True csv=False level=5\n"


def test_two_parameters_conflict():
    calls = []
    result = CliRunner().invoke(_format_cli(calls), ["--json", "--yaml"])
    assert result.exit_code == 2
    assert "Error: Parameters '--json' and '--yaml' cannot be used together." in (
        result.output
    )
    assert calls == []


def test_three_parameters_message():
    result = CliRunner().invoke(_format_cli(), ["--csv", "--json", "--yaml"])
    assert result.exit_code == 2
    assert (
        "Parameters '--json', '--yaml' and '--csv' cannot be used together."
        in result.output
    )


def test_defaults_do_not_count_as_provided():
    @click.command(mutually_exclusive=[("fast", "level")])
    @click.option("--fast", is_flag=True, default=False)
    @click.option("--level", type=int, default=3)
    def cli(fast, level):
        click.echo(f"{fast} {level}")

    runner = CliRunner()
    assert runner.invoke(cli, ["--fast"]).output == "True 3\n"
    assert runner.invoke(cli, ["--level", "9"]).output == "False 9\n"
    assert runner.invoke(cli, []).output == "False 3\n"
    assert runner.invoke(cli, ["--fast", "--level", "1"]).exit_code == 2


def test_environment_variable_counts_as_provided():
    runner = CliRunner()
    result = runner.invoke(_format_cli(), ["--json"], env={"TV_YAML": "1"})
    assert result.exit_code == 2
    assert "'--json' and '--yaml' cannot be used together" in result.output
    result = runner.invoke(_format_cli(), [], env={"TV_YAML": "1"})
    assert result.output == "json=False yaml=True csv=False level=3\n"


def test_default_map_does_not_count():
    result = CliRunner().invoke(
        _format_cli(), ["--json"], default_map={"as_yaml": True}
    )
    assert result.exit_code == 0, result.output
    assert result.output.startswith("json=True yaml=True")


def test_groups_are_independent():
    @click.command(mutually_exclusive=[("a", "b"), ("c", "d")])
    @click.option("-a", is_flag=True)
    @click.option("-b", is_flag=True)
    @click.option("-c", is_flag=True)
    @click.option("-d", is_flag=True)
    def cli(a, b, c, d):
        click.echo("ran")

    runner = CliRunner()
    assert runner.invoke(cli, ["-a", "-c"]).output == "ran\n"
    result = runner.invoke(cli, ["-a", "-c", "-d"])
    assert result.exit_code == 2
    assert "Parameters '-c' and '-d' cannot be used together." in result.output


def test_flag_off_switch_and_arguments_count():
    @click.command(mutually_exclusive=[("color", "plain"), ("source", "stdin")])
    @click.option("--color/--no-color", default=True)
    @click.option("--plain", is_flag=True)
    @click.option("--stdin", is_flag=True)
    @click.argument("source", required=False)
    def cli(color, plain, source, stdin):
        click.echo("ran")

    runner = CliRunner()
    result = runner.invoke(cli, ["--no-color", "--plain"])
    assert result.exit_code == 2
    assert "Parameters '--color' and '--plain' cannot be used together." in result.output
    result = runner.invoke(cli, ["--stdin", "file.txt"])
    assert result.exit_code == 2
    assert "Parameters '[SOURCE]' and '--stdin' cannot be used together." in result.output
    assert runner.invoke(cli, ["file.txt"]).output == "ran\n"


def test_group_parameters_are_checked_before_subcommand():
    calls = []

    @click.group(mutually_exclusive=[("verbose", "quiet")])
    @click.option("--verbose", is_flag=True)
    @click.option("--quiet", is_flag=True)
    def cli(verbose, quiet):
        calls.append("group")

    @cli.command()
    def sub():
        calls.append("sub")

    runner = CliRunner()
    result = runner.invoke(cli, ["--verbose", "--quiet", "sub"])
    assert result.exit_code == 2
    assert "Parameters '--verbose' and '--quiet' cannot be used together." in (
        result.output
    )
    assert calls == []
    assert runner.invoke(cli, ["--quiet", "sub"]).exit_code == 0
    assert calls == ["group", "sub"]


def test_group_needs_two_different_names():
    with pytest.raises(ValueError, match="at least two different parameter names"):
        click.Command("c", mutually_exclusive=[("json",)])
    with pytest.raises(ValueError):
        click.Command("c", mutually_exclusive=[("json", "json")])


def test_unknown_parameter_name_is_a_type_error():
    @click.command(mutually_exclusive=[("json", "missing")])
    @click.option("--json", is_flag=True)
    def cli(json):
        pass

    result = CliRunner().invoke(cli, [])
    assert isinstance(result.exception, TypeError)
    assert "'missing'" in str(result.exception)


def test_check_is_skipped_during_resilient_parsing():
    cli = _format_cli()
    ctx = cli.make_context("cli", ["--json", "--yaml"], resilient_parsing=True)
    assert ctx.params["as_json"] is True
    assert ctx.params["as_yaml"] is True
    with pytest.raises(click.UsageError):
        cli.make_context("cli", ["--json", "--yaml"])
