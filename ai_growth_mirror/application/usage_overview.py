"""Application-owned Usage Overview section assembly."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..domain.growth.model import GrowthProfile
from ..domain.session.model import SessionRecord
from .label_catalogs import ReportLabelCatalogs


@dataclass
class UsageStatView:
    label: str
    value: str
    detail: str = ""


@dataclass
class UsageSectionView:
    headline: str
    summary: str
    hero_support_line: str = ""
    coverage_note: str = ""
    memory_note: str = ""
    stats: list[UsageStatView] = field(default_factory=list)


def _view_i18n(catalogs: ReportLabelCatalogs) -> dict:
    return catalogs.view_model


def _format_compact_number(value: int | float, compact_number_units: list) -> str:
    absolute = abs(float(value))
    for unit in compact_number_units:
        threshold = int(unit.get("threshold", 0) or 0)
        suffix = str(unit.get("suffix", "") or "")
        if threshold > 0 and absolute >= threshold:
            scaled = value / threshold
            digits = 1 if abs(scaled) < 100 else 0
            return f"{scaled:.{digits}f}".rstrip("0").rstrip(".") + suffix
    return f"{int(round(value))}"


def _format_currency_compact(amount: float | None) -> str:
    if amount is None or amount <= 0:
        return "--"
    absolute = abs(amount)
    if absolute >= 1_000_000:
        scaled, suffix = amount / 1_000_000, "M"
    elif absolute >= 1_000:
        scaled, suffix = amount / 1_000, "k"
    else:
        return f"${amount:.2f}".rstrip("0").rstrip(".")
    digits = 1 if abs(scaled) < 100 else 0
    return f"${scaled:.{digits}f}".rstrip("0").rstrip(".") + suffix


def build_usage_coverage_note(
    sessions: list[SessionRecord],
    catalogs: ReportLabelCatalogs,
) -> str:
    usage_i18n = _view_i18n(catalogs).get("usage_overview", {})
    tool_labels = {
        "codex": "Codex CLI",
        "cursor": "Cursor",
        "claude": "Claude Code",
        "claude_code": "Claude Code",
        "trae": "Trae",
        "qoder": "Qoder",
        "cline": "Cline",
        "kilo": "Kilo Code",
    }
    tool_has_usage: dict[str, bool] = {}
    for session in sessions:
        tool = session.tool_name or "unknown"
        has_usage = any(
            value not in (None, 0)
            for value in (
                session.input_tokens,
                session.output_tokens,
                session.cache_read_tokens,
                session.cache_write_tokens,
            )
        )
        tool_has_usage[tool] = tool_has_usage.get(tool, False) or has_usage
    if not tool_has_usage:
        return ""
    covered = [tool_labels.get(tool, tool) for tool, has_usage in tool_has_usage.items() if has_usage]
    missing = [tool_labels.get(tool, tool) for tool, has_usage in tool_has_usage.items() if not has_usage]
    if covered and missing:
        return usage_i18n.get("coverage_note_partial", "").format(
            covered=" / ".join(covered),
            missing=" / ".join(missing),
        )
    if not covered and missing:
        return usage_i18n.get("coverage_note_none", "").format(
            missing=" / ".join(missing),
        )
    return ""


def build_usage_section(stats: GrowthProfile, catalogs: ReportLabelCatalogs) -> UsageSectionView:
    usage_i18n = _view_i18n(catalogs).get("usage_overview", {})
    compact_number_units = usage_i18n.get("compact_number_units", [])
    total_tokens = (
        (getattr(stats, "total_input_tokens", 0) or 0)
        + (getattr(stats, "total_output_tokens", 0) or 0)
        + (getattr(stats, "total_cache_read_tokens", 0) or 0)
        + (getattr(stats, "total_cache_write_tokens", 0) or 0)
    )
    token_volume_display = (
        usage_i18n.get("unknown_usage", "--")
        if total_tokens <= 0
        else _format_compact_number(total_tokens, compact_number_units)
    )
    cache_hit_rate = getattr(stats, "avg_cache_hit_rate", None)
    cache_read_tokens = getattr(stats, "total_cache_read_tokens", 0) or 0
    cache_write_tokens = getattr(stats, "total_cache_write_tokens", 0) or 0
    cache_hit_display = (
        "0%"
        if cache_hit_rate is None and (cache_read_tokens + cache_write_tokens) == 0
        else usage_i18n.get("unknown_cache", "--")
        if cache_hit_rate is None
        else f"{round(cache_hit_rate * 100)}%"
    )
    cost_display = (
        usage_i18n.get("unknown_cost", "--")
        if (getattr(stats, "total_cost_usd", 0.0) or 0.0) <= 0
        else _format_currency_compact(stats.total_cost_usd)
    )
    avg_cost_display = (
        usage_i18n.get("unknown_cost", "--")
        if (getattr(stats, "avg_cost_per_session", 0.0) or 0.0) <= 0
        else _format_currency_compact(stats.avg_cost_per_session)
    )
    advanced_ratio_pct = round((getattr(stats, "advanced_feature_ratio", 0.0) or 0.0) * 100)
    mcp_rate = round((getattr(stats, "mcp_session_rate", 0.0) or 0.0) * 100)
    subagent_count = getattr(stats, "subagent_session_count", 0)
    heavy_count = getattr(stats, "heavy_session_count", 0)
    avg_chain = round(getattr(stats, "avg_autonomous_chain_length", 0.0) or 0.0, 1)
    median_minutes = int(round(getattr(stats, "median_session_duration_minutes", 0.0) or 0.0))
    total_calls = sum(count for _name, count in getattr(stats, "top_tools", []))

    summary = usage_i18n.get("summary", "").format(
        session_count=stats.session_count,
        tool_calls=total_calls,
        token_volume=token_volume_display,
        advanced_feature_ratio=advanced_ratio_pct,
    )
    hero_support_line = usage_i18n.get("hero_support_line", "").format(
        summary=summary,
        total_cost=cost_display,
        avg_cost=avg_cost_display,
        cache_hit=cache_hit_display,
    )
    stats_cards = [
        UsageStatView(
            label=usage_i18n.get("token_card_label", "Token 体量"),
            value=usage_i18n.get("token_card_value", "{token_volume}").format(token_volume=token_volume_display),
            detail=usage_i18n.get("token_card_detail", "").format(
                input_tokens=_format_compact_number(getattr(stats, "total_input_tokens", 0) or 0, compact_number_units),
                output_tokens=_format_compact_number(getattr(stats, "total_output_tokens", 0) or 0, compact_number_units),
                cache_tokens=_format_compact_number(cache_read_tokens + cache_write_tokens, compact_number_units),
            ),
        ),
        UsageStatView(
            label=usage_i18n.get("cache_card_label", "成本 / 缓存"),
            value=usage_i18n.get("cache_card_value", "{total_cost} · {cache_hit}").format(
                total_cost=cost_display,
                cache_hit=cache_hit_display,
            ),
            detail=usage_i18n.get("cache_card_detail", "").format(
                avg_cost=avg_cost_display,
                cache_read=_format_compact_number(cache_read_tokens, compact_number_units),
                cache_write=_format_compact_number(cache_write_tokens, compact_number_units),
                cache_hit=cache_hit_display,
            ),
        ),
        UsageStatView(
            label=usage_i18n.get("leverage_card_label", "高杠杆使用"),
            value=usage_i18n.get("leverage_card_value", "{advanced_feature_ratio}%").format(
                advanced_feature_ratio=advanced_ratio_pct
            ),
            detail=usage_i18n.get("leverage_card_detail", "").format(
                subagent_count=subagent_count,
                mcp_rate=mcp_rate,
                tool_diversity=getattr(stats, "tier_diversity_count", 0),
            ),
        ),
        UsageStatView(
            label=usage_i18n.get("intensity_card_label", "协作强度"),
            value=usage_i18n.get("intensity_card_value", "{avg_chain}").format(avg_chain=avg_chain),
            detail=usage_i18n.get("intensity_card_detail", "").format(
                median_minutes=median_minutes,
                heavy_count=heavy_count,
            ),
        ),
    ]
    return UsageSectionView(
        headline=usage_i18n.get("headline", ""),
        summary=summary,
        hero_support_line=hero_support_line,
        memory_note=usage_i18n.get("memory_note", ""),
        stats=stats_cards,
    )
