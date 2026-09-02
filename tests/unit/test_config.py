"""Configuration contract tests introduced by v1.0.1."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from ai_growth_mirror.config import GrowthMirrorConfig


def test_weekly_session_target_defaults_to_eight() -> None:
    assert GrowthMirrorConfig().report.weekly_session_target == 8


def test_weekly_session_target_loads_positive_integer(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("report:\n  weekly_session_target: 12\n", encoding="utf-8")

    assert GrowthMirrorConfig.load(config_path).report.weekly_session_target == 12


@pytest.mark.parametrize("value", ["0", "-1", "true", "1.5", "invalid"])
def test_weekly_session_target_rejects_invalid_values(tmp_path: Path, value: str) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(f"report:\n  weekly_session_target: {value}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="weekly_session_target"):
        GrowthMirrorConfig.load(config_path)


def test_config_example_projects_the_runtime_default() -> None:
    example_path = Path(__file__).resolve().parents[2] / "config.example.yaml"
    example = yaml.safe_load(example_path.read_text(encoding="utf-8"))
    assert example["report"]["weekly_session_target"] == (
        GrowthMirrorConfig().report.weekly_session_target
    )
