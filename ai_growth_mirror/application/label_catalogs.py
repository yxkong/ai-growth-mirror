"""Application-owned report label catalogs and loader."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..infra.i18n.catalog import load_catalog


STATUS_LABEL_KEYS = (
    "title",
    "weekly_window",
    "weekly_sessions",
    "weekly_progress",
    "contract_title",
    "target",
    "success_signal",
    "action",
    "no_contract",
    "first_run",
)


@dataclass(frozen=True)
class ReportLabelCatalogs:
    """Preloaded label catalogs injected into report view assembly."""

    view_model: dict[str, Any]
    level_guide: dict[str, Any]
    template_labels: dict[str, str]
    growth_plan: dict[str, Any]
    guidance_labels: dict[str, Any]
    collaboration_style: dict[str, Any]
    language: str = "zh"


def load_report_label_catalogs(language: str = "zh") -> ReportLabelCatalogs:
    """Preload all YAML catalogs required by report assembly and rendering."""
    return ReportLabelCatalogs(
        view_model=load_catalog("view_model", language),
        level_guide=load_catalog("level_guide", language),
        template_labels=load_catalog("template_labels", language),
        growth_plan=load_catalog("growth_plan", language),
        guidance_labels=load_catalog("guidance_labels", language),
        collaboration_style=load_catalog("collaboration_style", language),
        language=language,
    )


def load_status_labels(language: str = "zh") -> dict[str, str]:
    """Load the CLI status copy from its single i18n source."""
    catalog = load_catalog("status", language)
    expected = set(STATUS_LABEL_KEYS)
    actual = set(catalog)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ValueError(
            f"status catalog schema mismatch: missing={missing}, extra={extra}"
        )
    if any(not isinstance(catalog[key], str) for key in STATUS_LABEL_KEYS):
        raise ValueError("status catalog values must be strings")
    return {key: catalog[key] for key in STATUS_LABEL_KEYS}
