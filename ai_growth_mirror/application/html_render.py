"""Pure HTML rendering for personal report surfaces (no I/O, no LLM)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from jinja2 import Environment, FileSystemLoader

from ..assets import ASSETS_DIR, TEMPLATES_DIR

if TYPE_CHECKING:
    from .report_view import PersonalReportView
    from .growth_trajectory import SnapshotComparisonPageView


def _jinja_env() -> Environment:
    return Environment(
        loader=FileSystemLoader([str(TEMPLATES_DIR), str(ASSETS_DIR)]),
        autoescape=True,
    )


def render_personal_report_html(
    *,
    view: PersonalReportView,
    language: str = "zh",
    redact: bool = False,
    now: datetime | None = None,
) -> str:
    env = _jinja_env()
    tmpl = env.get_template("report.html.j2")
    return tmpl.render(
        view=view,
        now=now or datetime.now(),
        language=language,
        redact=redact,
        theme_variant="personal",
    )


def render_share_card_html(
    *,
    summary_payload: dict[str, Any],
    template_labels: dict[str, str],
    language: str = "zh",
) -> str:
    labels = template_labels
    env = _jinja_env()
    template = env.get_template("share_card.html.j2")
    return template.render(
        payload=summary_payload,
        share_card=summary_payload.get("share_card", {}),
        labels=labels,
        language=language,
        theme_variant="personal",
    )


def render_snapshot_compare_html(
    *,
    page: "SnapshotComparisonPageView",
    template_labels: dict[str, str],
    language: str = "zh",
) -> str:
    env = _jinja_env()
    template = env.get_template("snapshot_compare.html.j2")
    return template.render(
        page=page,
        labels=template_labels,
        language=language,
        theme_variant="snapshot",
    )
