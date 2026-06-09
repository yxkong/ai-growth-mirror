"""Effective task-contract signal enrichment."""

from __future__ import annotations

from .model import SessionRecord

_ACCEPTANCE_PATTERNS = (
    "验收",
    "完成标准",
    "通过标准",
    "done-state",
    "done state",
    "acceptance",
    "success signal",
    "test plan",
    "通过为准",
    "算通过",
)
_BOUNDARY_PATTERNS = (
    "范围",
    "边界",
    "白名单",
    "黑名单",
    "只改",
    "仅改",
    "不要改",
    "不允许",
    "禁止",
    "scope",
    "boundary",
    "only change",
    "do not change",
    "must not",
)
_VALIDATION_PATTERNS = (
    "验证",
    "测试",
    "冒烟",
    "构建",
    "编译",
    "跑",
    "pytest",
    "npm run",
    "mvn",
    "gradle",
    "build",
    "compile",
    "test",
    "smoke",
    "verify",
)
_AGENT_CONTRACT_PATTERNS = (
    "实现阶段",
    "路由：",
    "delivery-workflow",
    "test plan",
    "验证路径",
    "验收标准",
    "完成标准",
    "checkpoint",
)
_LATE_CORRECTION_PATTERNS = (
    "你为啥",
    "为什么要",
    "按照规范",
    "按规范",
    "不要使用子agent",
    "不要子agent",
    "不是这个范围",
    "不能默认",
    "不要默认值",
    "不对",
    "还是不对",
    "你改错",
    "跑偏",
    "scope drift",
    "wrong scope",
)


def is_indexed_prompt_session(session: SessionRecord) -> bool:
    """A session that anchors on a known skill/slash-command/rule entry.

    Such sessions are high signal even when they have only one user message:
    the user is leveraging accumulated assets rather than re-typing context.
    """
    return bool(
        session.skill_invocation_count > 0
        or session.unique_skills_used
        or session.slash_commands
    )


def _contains_any(text: str, patterns: tuple[str, ...]) -> bool:
    if not text:
        return False
    lower = text.lower()
    return any(pattern.lower() in lower for pattern in patterns)


def _append_unique(values: list[str], value: str) -> None:
    if value and value not in values:
        values.append(value)


def enrich_task_contract_signals(session: SessionRecord) -> None:
    """Infer where the effective task contract came from.

    The output is intentionally conservative. Unknown is preferable to turning
    weak keyword evidence into a hard conclusion.
    """
    first_prompt = session.first_prompt or ""
    user_messages = session.top_user_messages or []
    follow_ups = user_messages[1:] if len(user_messages) > 1 else []
    sources = list(session.task_contract_sources or [])

    explicit_acceptance = _contains_any(first_prompt, _ACCEPTANCE_PATTERNS)
    explicit_boundary = _contains_any(first_prompt, _BOUNDARY_PATTERNS)
    explicit_validation = _contains_any(first_prompt, _VALIDATION_PATTERNS)
    explicit_user = explicit_acceptance or explicit_boundary or explicit_validation
    if explicit_user:
        _append_unique(sources, "explicit_user")

    indexed = is_indexed_prompt_session(session)
    if session.unique_skills_used or session.skill_invocation_count > 0:
        _append_unique(sources, "skill_read")
    if session.slash_commands or "plan_mode" in (session.advanced_features or []):
        _append_unique(sources, "workflow_rule")
    if indexed and "skill_read" not in sources and "workflow_rule" not in sources:
        _append_unique(sources, "attached_skill")

    assistant_msgs = getattr(session, "assistant_messages", []) or []
    full_session_text = "\n".join([first_prompt, *user_messages, *assistant_msgs])

    if _contains_any(full_session_text, _AGENT_CONTRACT_PATTERNS):
        _append_unique(sources, "agent_derived")

    late_correction = any(
        _contains_any(message, _LATE_CORRECTION_PATTERNS)
        for message in follow_ups
    )
    session.late_contract_correction = bool(session.late_contract_correction or late_correction)
    if session.late_contract_correction:
        _append_unique(sources, "late_user")

    if not sources:
        sources = ["missing"] if first_prompt or user_messages else ["unknown"]
    session.task_contract_sources = sources

    def _source_for(explicit: bool, kind_patterns: tuple[str, ...]) -> str:
        if explicit:
            return "explicit_user"

        if not _contains_any(full_session_text, kind_patterns):
            return "missing" if "missing" in sources else "unknown"

        if "skill_read" in sources:
            return "skill_read"
        if "workflow_rule" in sources:
            return "workflow_rule"
        if "attached_skill" in sources:
            return "attached_skill"
        if "agent_derived" in sources:
            return "agent_derived"
        if "late_user" in sources:
            return "late_user"
        return "missing" if "missing" in sources else "unknown"

    session.acceptance_contract_source = _source_for(explicit_acceptance, _ACCEPTANCE_PATTERNS)
    session.boundary_contract_source = _source_for(explicit_boundary, _BOUNDARY_PATTERNS)
    session.validation_contract_source = _source_for(explicit_validation, _VALIDATION_PATTERNS)

    valid_sources = {"explicit_user", "skill_read", "workflow_rule", "attached_skill", "agent_derived"}
    session.pre_execution_contract_present = (
        session.acceptance_contract_source in valid_sources
        or session.boundary_contract_source in valid_sources
        or session.validation_contract_source in valid_sources
    )

    if session.has_verification_behavior or session.has_test_commands:
        session.agent_contract_compliance = "met" if session.pre_execution_contract_present else "partial"
    elif session.pre_execution_contract_present and (session.files_modified > 0 or session.tool_counts):
        session.agent_contract_compliance = "missing"
    elif session.pre_execution_contract_present:
        session.agent_contract_compliance = "partial"
    else:
        session.agent_contract_compliance = "unknown"
