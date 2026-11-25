import click
from click.testing import CliRunner


def _help(cli, args=("--help",)):
    result = CliRunner().invoke(cli, list(args), terminal_width=100)
    assert result.exit_code == 0, result.output
    return result.output


def _sections(text):
    """Map each help heading to the option names listed under it, in order."""
    sections = {}
    current = None
    for line in text.splitlines():
        if line and not line.startswith(" ") and line.endswith(":"):
            current = line[:-1]
            sections[current] = []
        elif current is not None and line.startswith("  -"):
            sections[current].append(line.split()[0].rstrip(","))
    return sections


def _server():
    @click.command()
    @click.option("--verbose", is_flag=True, help="Verbose output.")
    @click.option("--host", help_section="Network", help="Host to bind.")
    @click.option("--json", "as_json", is_flag=True, help_section="Output")
    @click.option("--port", type=int, default=8080, show_default=True, help_section="Network")
    @click.option("--secret", hidden=True, help_section="Hidden")
    def cli(verbose, host, as_json, port, secret):
        pass

    return cli


def test_option_stores_help_section():
    assert click.Option(["--host"], help_section="Network").help_section == "Network"
    assert click.Option(["--host"], help_section=None).help_section is None
    assert click.Option(["--host"]).help_section is None


def test_options_are_grouped_under_their_sections():
    sections = _sections(_help(_server()))
    assert sections["Network"] == ["--host", "--port"]
    assert sections["Output"] == ["--json"]


def test_unsectioned_options_and_help_stay_under_options():
    sections = _sections(_help(_server()))
    assert sections["Options"] == ["--verbose", "--help"]


def test_sections_follow_options_in_first_appearance_order():
    text = _help(_server())
    headings = [h for h in _sections(text) if h in {"Options", "Network", "Output"}]
    assert headings == ["Options", "Network", "Output"]
    assert text.index("Options:") < text.index("Network:") < text.index("Output:")


def test_order_is_by_first_appearance_not_alphabetical():
    @click.command()
    @click.option("--zeta", help_section="Zulu")
    @click.option("--alpha", help_section="Alpha")
    @click.option("--zed", help_section="Zulu")
    def cli(zeta, alpha, zed):
        pass

    sections = _sections(_help(cli))
    assert list(sections) == ["Options", "Zulu", "Alpha"]
    assert sections["Zulu"] == ["--zeta", "--zed"]


def test_hidden_options_never_create_a_section():
    text = _help(_server())
    assert "Hidden:" not in text
    assert "--secret" not in text


def test_no_options_heading_when_every_option_has_a_section():
    @click.command(add_help_option=False)
    @click.option("--host", help_section="Network")
    def cli(host):
        pass

    ctx = click.Context(cli)
    text = cli.get_help(ctx)
    assert "Options:" not in text
    assert _sections(text) == {"Network": ["--host"]}


def test_records_keep_their_usual_rendering():
    text = _help(_server())
    port_line = next(line for line in text.splitlines() if "--port" in line)
    assert "--port INTEGER" in port_line
    assert "[default: 8080]" in port_line
    host_line = next(line for line in text.splitlines() if "--host" in line)
    assert "Host to bind." in host_line


def test_help_without_sections_is_unchanged():
    @click.command()
    @click.option("--name", help="Your name.", help_section=None)
    @click.argument("path", help="A path.")
    def explicit(name, path):
        """Do things."""

    @click.command()
    @click.option("--name", help="Your name.")
    @click.argument("path", help="A path.")
    def implicit(name, path):
        """Do things."""

    explicit_help = _help(explicit)
    assert explicit_help == _help(implicit).replace("implicit", "explicit")
    assert _sections(explicit_help)["Options"] == ["--name", "--help"]


def test_group_sections_come_before_commands():
    @click.group()
    @click.option("--profile", help_section="Configuration")
    def cli(profile):
        pass

    @cli.command()
    def deploy():
        """Deploy it."""

    text = _help(cli)
    assert text.index("Options:") < text.index("Configuration:") < text.index("Commands:")
    assert _sections(text)["Configuration"] == ["--profile"]


def test_arguments_section_is_unaffected():
    @click.command()
    @click.argument("src", help="Source file.")
    @click.option("--force", is_flag=True, help_section="Safety")
    def cli(src, force):
        pass

    text = _help(cli)
    assert text.index("Positional arguments:") < text.index("Options:")
    assert text.index("Options:") < text.index("Safety:")
    assert _sections(text)["Safety"] == ["--force"]
