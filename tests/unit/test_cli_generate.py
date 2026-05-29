from pathlib import Path

import click.testing

from ai_growth_mirror.application.orchestrator import (
    GenerateReportRequest,
    GenerateReportResult,
    NoToolDataError,
)
from ai_growth_mirror.cli import cli


def test_cli_generate_delegates_to_orchestrator(monkeypatch):
    captured: dict = {}

    def fake_generate(request: GenerateReportRequest) -> GenerateReportResult:
        captured["request"] = request
        return GenerateReportResult(
            output_path=Path("ai-growth-mirror.html"),
            display_name="Codex CLI",
            session_count=12,
            session_read_count=12,
            session_read_mode="heuristic",
            growth_level="L2",
            mirror_score=55.0,
        )

    monkeypatch.setattr(
        "ai_growth_mirror.cli.generate_report_artifacts",
        fake_generate,
    )

    runner = click.testing.CliRunner()
    result = runner.invoke(
        cli,
        [
            "generate",
            "--tools",
            "codex",
            "--session-read-mode",
            "heuristic",
            "--output",
            "ai-growth-mirror.html",
        ],
    )

    assert result.exit_code == 0, result.output
    request = captured["request"]
    assert request.tools == ["codex"]
    assert request.session_read_mode == "heuristic"
    assert request.write_manifest is True
    assert request.output_path.name == "ai-growth-mirror.html"
    assert "done total=" in result.output


def test_cli_generate_maps_no_tool_data_error(monkeypatch):
    def fake_generate(_request: GenerateReportRequest):
        raise NoToolDataError(tool_names=["codex"])

    monkeypatch.setattr(
        "ai_growth_mirror.cli.generate_report_artifacts",
        fake_generate,
    )

    runner = click.testing.CliRunner()
    result = runner.invoke(
        cli,
        ["generate", "--tools", "codex", "--session-read-mode", "heuristic"],
    )

    assert result.exit_code == 1
    assert "No AI coding tool data found" in result.output


def test_cli_help_lists_generate_command():
    runner = click.testing.CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "generate" in result.output
