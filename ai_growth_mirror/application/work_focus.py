"""Application-owned Work Focus section assembly."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from ..domain.growth.model import GrowthProfile
from ..domain.session.model import SessionRecord
from ..domain.signals.model import SessionRead
from .label_catalogs import ReportLabelCatalogs

if TYPE_CHECKING:
    from ..domain.common.contracts import LlmGateway


@dataclass
class FocusAreaView:
    label: str
    count: int
    detail: str = ""


@dataclass
class WorkFocusSectionView:
    headline: str
    recent_work: list[str] = field(default_factory=list)
    goal_mix: list[FocusAreaView] = field(default_factory=list)
    tools: list[FocusAreaView] = field(default_factory=list)
    languages: list[FocusAreaView] = field(default_factory=list)


def _view_i18n(catalogs: ReportLabelCatalogs) -> dict:
    return catalogs.view_model


def _trim_text(value: str, limit: int) -> str:
    text = (value or "").replace("\n", " ").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _goal_label(name: str, catalogs: ReportLabelCatalogs) -> str:
    labels = _view_i18n(catalogs).get("goal_labels", {})
    return labels.get(name, name)


def _display_tool_name(name: str, catalogs: ReportLabelCatalogs) -> str:
    mapping = _view_i18n(catalogs).get("tool_labels", {})
    if name.startswith("mcp__"):
        return _view_i18n(catalogs).get("tool_label_mcp", "MCP tool")
    return mapping.get(name, name.replace("_", " "))


def _primary_goal_from_session_reads(session_reads: list[SessionRead], catalogs: ReportLabelCatalogs) -> str:
    counts: dict[str, int] = {}
    for read in session_reads or []:
        if read.confidence == "low":
            continue
        for key, count in (read.work_intent_mix or {}).items():
            counts[key] = counts.get(key, 0) + int(count or 0)
    if not counts:
        return ""
    primary_key = max(counts.items(), key=lambda item: item[1])[0]
    return _goal_label(primary_key, catalogs)


def _recent_work_items(
    sessions: list[SessionRecord],
    session_reads: list[SessionRead],
    catalogs: ReportLabelCatalogs,
) -> list[str]:
    count_suffix = _view_i18n(catalogs).get("work_focus", {}).get(
        "recent_work_count_suffix",
        "",
    )

    candidates: list[str] = []
    read_by_session = {read.session_id: read for read in session_reads or []}
    sorted_sessions = sorted(
        sessions,
        key=lambda session: session.start_time or "",
        reverse=True,
    )
    for session in sorted_sessions:
        read = read_by_session.get(session.session_id)
        item = _work_item_from_session_read(read) if read else ""
        if not item:
            source = session.first_prompt or (session.top_user_messages[0] if session.top_user_messages else "")
            item = _finalize_work_item(source, _work_item_from_prompt(source))
        if item:
            candidates.append(item)

    unique_candidates = []
    for c in candidates:
        if c not in unique_candidates:
            unique_candidates.append(c)

    if len(unique_candidates) <= 2:
        return unique_candidates[:4]

    sorted_topics = _cluster_work_items(candidates)
    results: list[str] = []
    for topic_name, count in sorted_topics:
        suffix = count_suffix.format(count=count) if count_suffix and count > 1 else ""
        results.append(f"{topic_name}{suffix}")
        if len(results) >= 4:
            break

    return results


def _cluster_work_items(items: list[str]) -> list[tuple[str, int]]:
    clusters: list[tuple[str, int]] = []
    for item in items:
        label = _compact_work_item_label(item)
        if not label:
            continue
        matched = False
        for index, (existing, count) in enumerate(clusters):
            if _work_items_related(existing, label):
                clusters[index] = (existing if len(existing) >= len(label) else label, count + 1)
                matched = True
                break
        if not matched:
            clusters.append((label, 1))
    ranked = sorted(enumerate(clusters), key=lambda row: (-row[1][1], row[0]))
    return [item for _, item in ranked]


def _compact_work_item_label(value: str) -> str:
    text = _sanitize_work_item_source(value)
    stripped = re.sub(
        r"^(实现|修复|优化|完善|搭建|补充|整理|重构|分析|推进|设计)\s*",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip(" ：:，,、")
    if _is_meaningful_work_item(stripped):
        text = stripped
    if not _is_meaningful_work_item(text):
        return ""
    return _trim_text(text, 32)


def _work_items_related(left: str, right: str) -> bool:
    left_key = _work_item_key(left)
    right_key = _work_item_key(right)
    if not left_key or not right_key:
        return False
    if left_key in right_key or right_key in left_key:
        return True
    left_tokens = set(re.findall(r"[A-Za-z0-9_+-]{3,}|[\u4e00-\u9fff]{2,}", left_key))
    right_tokens = set(re.findall(r"[A-Za-z0-9_+-]{3,}|[\u4e00-\u9fff]{2,}", right_key))
    if not left_tokens or not right_tokens:
        return False
    return bool(left_tokens & right_tokens)


def _work_item_key(value: str) -> str:
    return re.sub(r"[\s：:，,。；;.!?、（）()【】\[\]\"'`]+", "", value.lower())


def _is_meaningful_work_item(value: str) -> bool:
    text = (value or "").strip()
    if len(text) < 4:
        return False
    cjk_count = len(re.findall(r"[\u4e00-\u9fff]", text))
    alnum_count = len(re.findall(r"[A-Za-z0-9]", text))
    if cjk_count < 2 and alnum_count < 8:
        return False
    for pattern in _JUNK_WORK_ITEM_PATTERNS:
        if pattern.search(text):
            return False
    if re.fullmatch(r"#\w+", text):
        return False
    return True


def _looks_like_raw_prompt(value: str) -> bool:
    text = (value or "").strip()
    if len(text) > 72:
        return True
    return bool(
        re.search(
            r"git@|github\.com|/Users/|/home/|^[#`]|(?:^|\s)review(?:\s|$)",
            text,
            flags=re.IGNORECASE,
        )
    )


def _work_item_from_session_read(read: SessionRead | None) -> str:
    if not read or read.confidence == "low" or not read.work_summary:
        return ""
    return _normalize_work_item_text(read.work_summary)


def _finalize_work_item(source: str, item: str) -> str:
    if not item or not _is_meaningful_work_item(item):
        return ""
    if _is_degraded_git_fragment(source, item):
        return ""
    return item


def _is_degraded_git_fragment(source: str, cleaned: str) -> bool:
    if not re.search(r"git@|github\.com|gitlab\.com|gitee\.com", source, flags=re.IGNORECASE):
        return False
    return bool(
        re.search(
            r"克隆|拉取|checkout|remote|仓库|repo",
            cleaned,
            flags=re.IGNORECASE,
        )
    )


def _normalize_work_item_text(source: str) -> str:
    if _looks_like_raw_prompt(source):
        parsed = _work_item_from_prompt(source)
        return _finalize_work_item(source, parsed)
    text = _sanitize_work_item_source(source)
    if not text:
        return ""
    return _finalize_work_item(source, _trim_text(text, 48))


_PATH_RE = re.compile(
    r"(?:[A-Za-z]:[\\/][^\s，。；;]+|/Users/[^\s，。；;]+|/home/[^\s，。；;]+|\\\\\?\\[^\s，。；;]+)"
)
_GIT_REMOTE_RE = re.compile(
    r"(?:git@[^\s，。；;]+|https?://(?:github|gitlab|gitee)\.com/[^\s，。；;]+)",
    flags=re.IGNORECASE,
)
_JUNK_WORK_ITEM_PATTERNS = (
    re.compile(r"git@|github\.com|gitlab\.com|gitee\.com", re.IGNORECASE),
    re.compile(r"^#\s*[A-Za-z][\w.-]*$"),
    re.compile(r"^把\s*(?:git|http)", re.IGNORECASE),
    re.compile(r"^https?://", re.IGNORECASE),
)
_WORK_ITEM_NOISE_PATTERNS = (
    r"^把\s*",
    r"^根据下面的内容\s*review\s*[，,、和并]*\s*",
    r"^review\s*[，,、和并]*\s*",
    r"^使用\s*$",
    r"^解决报错\s*",
    r"^实现下面的功能\s*[，,、和并]*\s*",
    r"^并完善相关的文档\s*",
    r"^修复\s*review\s*到的问题\s*[，,、和并]*\s*",
)


def _work_item_from_prompt(value: str) -> str:
    text = " ".join((value or "").replace("\n", " ").split())
    if not text:
        return ""
    text = _sanitize_work_item_source(text)
    for pattern in (
        r"(?:目标结果|目标|本次任务|任务|当前问题|本次对象)[:：]\s*([^。；;.!?\n]+)",
        r"(?:help me|please|请|帮我)\s*([^。；;.!?\n]+)",
    ):
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            candidate = match.group(1).strip(" ：:，,")
            if candidate:
                return _trim_text(candidate, 48)
    first_sentence = re.split(r"[。；;.!?]", text, maxsplit=1)[0].strip(" ：:，,")
    return _trim_text(first_sentence, 48)


def _sanitize_work_item_source(value: str) -> str:
    text = _PATH_RE.sub(" ", value)
    text = _GIT_REMOTE_RE.sub(" ", text)
    text = re.sub(r"^#\s*\S+\s*", "", text)
    text = re.sub(r"\s+", " ", text).strip(" ：:，,、。；;.!?")
    changed = True
    while changed:
        changed = False
        for pattern in _WORK_ITEM_NOISE_PATTERNS:
            new_text = re.sub(pattern, "", text, flags=re.IGNORECASE).strip(" ：:，,、。；;.!?")
            if new_text != text:
                text = new_text
                changed = True
    if not text:
        return ""
    return text


def _primary_work_label(recent_work: list[str]) -> str:
    if not recent_work:
        return ""
    return re.sub(r"（关联 \d+ 次会话）$", "", recent_work[0]).strip()


def _rollup_tool_labels(items: list[tuple[str, int]], catalogs: ReportLabelCatalogs) -> list[FocusAreaView]:
    merged: dict[str, int] = {}
    details: dict[str, list[str]] = {}
    for name, count in items:
        label = _display_tool_name(name, catalogs)
        merged[label] = merged.get(label, 0) + count
        details.setdefault(label, []).append(name)
    ranked = sorted(merged.items(), key=lambda item: (-item[1], item[0]))
    return [
        FocusAreaView(label=label, count=count, detail=" / ".join(sorted(set(details.get(label, [])))))
        for label, count in ranked
    ]


def _sanitize_work_focus_headline(value: str) -> str:
    text = _PATH_RE.sub(" ", value or "")
    text = _GIT_REMOTE_RE.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def _apply_llm_work_focus_output(payload: dict) -> tuple[str, list[str]] | None:
    headline = _trim_text(_sanitize_work_focus_headline(str(payload.get("headline", ""))), 120)
    if len(headline) < 8:
        return None
    recent_work: list[str] = []
    for entry in payload.get("recent_work") or []:
        if not isinstance(entry, str):
            continue
        item = _finalize_work_item(entry, _trim_text(_sanitize_work_item_source(entry), 48))
        if item:
            recent_work.append(item)
        if len(recent_work) >= 4:
            break
    if not recent_work:
        return None
    return headline, recent_work


def _build_rule_based_work_focus_narrative(
    sessions: list[SessionRecord],
    session_reads: list[SessionRead],
    catalogs: ReportLabelCatalogs,
    *,
    top_goals: list[FocusAreaView],
) -> tuple[str, list[str]]:
    recent_work = _recent_work_items(sessions, session_reads, catalogs)[:4]
    work_focus_i18n = _view_i18n(catalogs).get("work_focus", {})
    primary_goal = _primary_goal_from_session_reads(session_reads, catalogs) or (
        top_goals[0].label if top_goals else ""
    )
    primary_work = _primary_work_label(recent_work)
    headline_template = (
        work_focus_i18n.get("headline")
        if primary_goal and primary_work
        else work_focus_i18n.get("headline_goal_only")
        if primary_goal
        else work_focus_i18n.get("headline_work_only")
        if primary_work
        else work_focus_i18n.get("insufficient_headline")
    )
    headline = (headline_template or "").format(
        primary_goal=primary_goal,
        primary_work=primary_work,
    )
    return headline, recent_work


def build_work_focus(
    stats: GrowthProfile,
    sessions: list[SessionRecord],
    session_reads: list[SessionRead],
    redact: bool,
    catalogs: ReportLabelCatalogs,
    llm: Optional["LlmGateway"] = None,
    language: str | None = None,
) -> WorkFocusSectionView:
    total_goal_signals = max(sum(stats.goal_category_counts.values()), 1)
    top_goals = [
        FocusAreaView(
            label=_goal_label(name, catalogs),
            count=count,
            detail=(
                f"{round(count / total_goal_signals * 100)}%"
                if total_goal_signals > 0
                else ""
            ),
        )
        for name, count in sorted(stats.goal_category_counts.items(), key=lambda item: -item[1])[:4]
    ]
    top_tools = _rollup_tool_labels(stats.top_tools[:8], catalogs)[:5]
    top_languages = [FocusAreaView(label=name, count=count) for name, count in stats.top_languages[:4]]

    headline = ""
    recent_work: list[str] = []
    if not redact:
        if llm is not None:
            from ..infra.llm.work_focus import generate_work_focus_summary

            synthesis = generate_work_focus_summary(
                sessions=sessions,
                session_reads=session_reads,
                llm=llm,
                language=language or catalogs.language,
            )
            if synthesis:
                validated = _apply_llm_work_focus_output(synthesis)
                if validated:
                    headline, recent_work = validated
        if not headline and not recent_work:
            headline, recent_work = _build_rule_based_work_focus_narrative(
                sessions,
                session_reads,
                catalogs,
                top_goals=top_goals,
            )
    else:
        work_focus_i18n = _view_i18n(catalogs).get("work_focus", {})
        headline = work_focus_i18n.get("insufficient_headline", "")

    return WorkFocusSectionView(headline=headline, recent_work=recent_work, goal_mix=top_goals, tools=top_tools, languages=top_languages)
