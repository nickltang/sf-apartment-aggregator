from typer.testing import CliRunner

from sf_apartment_aggregator.cli import app


def test_cli_commands_exist() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "poll" in result.output
    assert "backfill" in result.output
    assert "dashboard" in result.output
