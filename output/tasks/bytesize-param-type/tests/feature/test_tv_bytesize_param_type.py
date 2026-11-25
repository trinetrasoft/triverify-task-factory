import pytest

import click
from click.testing import CliRunner


def _size(value, **kwargs):
    return click.ByteSize(**kwargs).convert(value, None, None)


def _error(value, **kwargs):
    with pytest.raises(click.BadParameter) as exc_info:
        _size(value, **kwargs)
    return exc_info.value.message


def test_plain_numbers_and_bytes_unit():
    assert _size("512") == 512
    assert _size("0") == 0
    assert _size("512B") == 512
    assert _size("7b") == 7


def test_every_unit_multiplier():
    expected = {
        "K": 1000,
        "KB": 1000,
        "M": 1000**2,
        "MB": 1000**2,
        "G": 1000**3,
        "GB": 1000**3,
        "T": 1000**4,
        "TB": 1000**4,
        "Ki": 1024,
        "KiB": 1024,
        "Mi": 1024**2,
        "MiB": 1024**2,
        "Gi": 1024**3,
        "GiB": 1024**3,
        "Ti": 1024**4,
        "TiB": 1024**4,
    }
    for unit, multiplier in expected.items():
        assert _size(f"3{unit}") == 3 * multiplier, unit


def test_units_are_case_insensitive_and_whitespace_tolerant():
    assert _size("10kb") == 10_000
    assert _size("2gib") == 2 * 1024**3
    assert _size(" 64 KB ") == 64_000
    assert _size("1 MiB") == 1024**2


def test_fractional_sizes_are_exact():
    assert _size("1.5MB") == 1_500_000
    assert _size("1.5 MiB") == 1_572_864
    assert _size("0.25KiB") == 256
    assert _size(".5KB") == 500
    assert _size("2.MB") == 2_000_000


def test_fraction_must_give_whole_bytes():
    assert "is not a whole number of bytes" in _error("0.5B")
    assert "is not a whole number of bytes" in _error("1.0001KB")
    assert _error("1.5") == "'1.5' is not a whole number of bytes."


def test_invalid_sizes():
    for value in ["abc", "-1KB", "1.2.3", "", "   ", ".", "KB"]:
        assert _error(value) == f"{value!r} is not a valid size.", value


def test_unknown_unit():
    assert _error("10 parsecs") == "'10 parsecs' has an unknown size unit 'parsecs'."
    assert _error("5XB") == "'5XB' has an unknown size unit 'XB'."


def test_integers_pass_through_and_booleans_do_not():
    assert _size(4096) == 4096
    assert _size(0) == 0
    assert _error(-1) == "-1 is not a valid size."
    with pytest.raises(click.BadParameter):
        _size(True)


def test_min_and_max_are_inclusive():
    assert _size("1KiB", min=1024) == 1024
    assert _size("1MiB", max=1024**2) == 1024**2
    assert _error("1KB", min=1024) == (
        "'1KB' is smaller than the minimum size of 1024 bytes."
    )
    assert _error("2MiB", max=1024**2) == (
        "'2MiB' is larger than the maximum size of 1048576 bytes."
    )


def test_command_line_integration():
    @click.command()
    @click.option("--cache", type=click.ByteSize(max=10**9), default="4KiB")
    def cli(cache):
        click.echo(repr(cache))

    runner = CliRunner()
    assert runner.invoke(cli, ["--cache", "1MiB"]).output == "1048576\n"
    assert runner.invoke(cli, []).output == "4096\n"

    result = runner.invoke(cli, ["--cache", "lots"])
    assert result.exit_code == 2
    assert "Invalid value for '--cache': 'lots' is not a valid size." in result.output

    result = runner.invoke(cli, ["--cache", "2GB"])
    assert result.exit_code == 2
    assert "larger than the maximum size of 1000000000 bytes" in result.output


def test_help_metavar_is_size():
    @click.command()
    @click.option("--limit", type=click.ByteSize(), help="Upload limit.")
    def cli(limit):
        pass

    result = CliRunner().invoke(cli, ["--help"])
    assert "--limit SIZE" in result.output


def test_info_dict_and_repr():
    size_type = click.ByteSize(min=1, max=1000)
    assert size_type.to_info_dict() == {
        "param_type": "ByteSize",
        "name": "size",
        "min": 1,
        "max": 1000,
    }
    assert click.ByteSize().to_info_dict()["min"] is None
    assert repr(click.ByteSize()) == "ByteSize"


def test_works_with_multiple_and_envvar():
    @click.command()
    @click.option("--size", type=click.ByteSize(), multiple=True, envvar="TV_SIZES")
    def cli(size):
        click.echo(sum(size))

    runner = CliRunner()
    assert runner.invoke(cli, ["--size", "1K", "--size", "1Ki"]).output == "2024\n"
    result = runner.invoke(cli, [], env={"TV_SIZES": "1KB 2KB"})
    assert result.output == "3000\n"
