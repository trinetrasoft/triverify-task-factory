import enum

import pytest

import click
from click.testing import CliRunner


def _convert(choice, value, ctx=None):
    return choice.convert(value, None, ctx)


def _error(choice, value, ctx=None):
    with pytest.raises(click.BadParameter) as exc_info:
        _convert(choice, value, ctx)
    return exc_info.value.message


def test_prefixes_are_rejected_when_disabled():
    choice = click.Choice(["json", "yaml"], allow_prefix=False)
    assert choice.allow_prefix is False
    assert _error(choice, "js") == "'js' is not one of 'json', 'yaml'."
    assert click.Choice(["a"]).allow_prefix is False


def test_unique_prefix_resolves_to_choice():
    choice = click.Choice(["json", "yaml", "toml"], allow_prefix=True)
    assert choice.allow_prefix is True
    assert _convert(choice, "js") == "json"
    assert _convert(choice, "y") == "yaml"
    assert _convert(choice, "toml") == "toml"


def test_exact_match_wins_over_longer_choice():
    choice = click.Choice(["dev", "development", "prod"], allow_prefix=True)
    assert _convert(choice, "dev") == "dev"
    assert _convert(choice, "deve") == "development"
    assert _convert(choice, "p") == "prod"


def test_ambiguous_prefix_lists_candidates_in_choice_order():
    choice = click.Choice(["test", "deploy", "debug"], allow_prefix=True)
    assert _error(choice, "de") == (
        "'de' is ambiguous; it could be one of 'deploy', 'debug'."
    )
    assert _convert(choice, "dep") == "deploy"


def test_unknown_value_keeps_invalid_choice_message():
    choice = click.Choice(["debug", "deploy"], allow_prefix=True)
    assert _error(choice, "x") == "'x' is not one of 'debug', 'deploy'."
    assert _error(choice, "debugger") == "'debugger' is not one of 'debug', 'deploy'."


def test_empty_value_is_not_a_prefix():
    choice = click.Choice(["only"], allow_prefix=True)
    assert _error(choice, "") == "'' is not 'only'."


def test_case_insensitive_prefix():
    choice = click.Choice(["Debug", "Release"], case_sensitive=False, allow_prefix=True)
    assert _convert(choice, "REL") == "Release"
    assert _convert(choice, "d") == "Debug"


def test_case_sensitive_prefix_respects_case():
    choice = click.Choice(["Debug", "debug-all"], allow_prefix=True)
    assert _convert(choice, "D") == "Debug"
    assert _convert(choice, "deb") == "debug-all"
    assert _error(choice, "DEB") == "'DEB' is not one of 'Debug', 'debug-all'."


def test_enum_choices_use_member_names():
    class Color(enum.Enum):
        RED = 1
        GREEN = 2
        GREY = 3

    choice = click.Choice(Color, allow_prefix=True)
    assert _convert(choice, "R") is Color.RED
    assert _error(choice, "GR") == "'GR' is ambiguous; it could be one of 'GREEN', 'GREY'."
    assert _convert(choice, "GREE") is Color.GREEN


def test_token_normalize_func_applies_to_prefixes():
    @click.command(context_settings={"token_normalize_func": str.lower})
    @click.option("--mode", type=click.Choice(["alpha", "beta"], allow_prefix=True))
    def cli(mode):
        click.echo(mode)

    result = CliRunner().invoke(cli, ["--mode", "AL"])
    assert result.exit_code == 0, result.output
    assert result.output == "alpha\n"


def test_command_line_errors():
    @click.command()
    @click.option(
        "--fmt", type=click.Choice(["json", "jsonl", "yaml"], allow_prefix=True)
    )
    def cli(fmt):
        click.echo(fmt)

    runner = CliRunner()
    assert runner.invoke(cli, ["--fmt", "y"]).output == "yaml\n"
    assert runner.invoke(cli, ["--fmt", "json"]).output == "json\n"
    assert runner.invoke(cli, ["--fmt", "jsonl"]).output == "jsonl\n"

    result = runner.invoke(cli, ["--fmt", "j"])
    assert result.exit_code == 2
    assert (
        "Invalid value for '--fmt': 'j' is ambiguous; it could be one of"
        " 'json', 'jsonl'." in result.output
    )


def test_info_dict_and_message_hook():
    choice = click.Choice(["a", "b"], allow_prefix=True)
    assert choice.to_info_dict() == {
        "param_type": "Choice",
        "name": "choice",
        "choices": ("a", "b"),
        "case_sensitive": True,
    }
    assert choice.get_ambiguous_choice_message("x", ["xa", "xb"], None) == (
        "'x' is ambiguous; it could be one of 'xa', 'xb'."
    )
