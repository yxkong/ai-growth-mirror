"""Domain tool-classification rules for session analytics."""

from __future__ import annotations

from collections import Counter

from .taxonomy import InteractionKind, ModelCapabilityTier

INTERACTION_KIND_DISPLAY: dict[InteractionKind, str] = {
    InteractionKind.INSPECT: "Inspect / search",
    InteractionKind.MODIFY: "Modify / edit",
    InteractionKind.EXECUTE: "Execute / shell",
    InteractionKind.EXTERNAL: "External / MCP",
    InteractionKind.BROWSE: "Browse / web",
    InteractionKind.WORKFLOW: "Workflow / skill",
    InteractionKind.DELEGATE: "Delegate / subagent",
    InteractionKind.ORGANIZE: "Organize / plan",
    InteractionKind.VALIDATE: "Validate / test",
    InteractionKind.VERSION: "Version / git",
    InteractionKind.CONTEXT_CTRL: "Context control",
    InteractionKind.MISC: "Miscellaneous",
}

INTERACTION_KIND_DISPLAY_ZH: dict[InteractionKind, str] = {
    InteractionKind.INSPECT: "检视/搜索",
    InteractionKind.MODIFY: "修改/编辑",
    InteractionKind.EXECUTE: "执行/终端",
    InteractionKind.EXTERNAL: "外部/MCP",
    InteractionKind.BROWSE: "浏览/联网",
    InteractionKind.WORKFLOW: "工作流/Skill",
    InteractionKind.DELEGATE: "委托/子代理",
    InteractionKind.ORGANIZE: "组织/规划",
    InteractionKind.VALIDATE: "验证/测试",
    InteractionKind.VERSION: "版本/Git",
    InteractionKind.CONTEXT_CTRL: "上下文控制",
    InteractionKind.MISC: "其他",
}

TOOL_TIER_DISPLAY = INTERACTION_KIND_DISPLAY
TOOL_TIER_DISPLAY_ZH = INTERACTION_KIND_DISPLAY_ZH


def infer_model_capability_tier(model_id: str) -> ModelCapabilityTier:
    normalized = (model_id or "").lower()
    if not normalized:
        return ModelCapabilityTier.TIER_2_STANDARD
    if "mini" in normalized or "haiku" in normalized:
        return ModelCapabilityTier.TIER_1_QUICK
    if "opus" in normalized or "o1" in normalized or ("pro" in normalized and "mini" not in normalized):
        return ModelCapabilityTier.TIER_3_PRO
    if "sonnet" in normalized or "gpt-4" in normalized:
        return ModelCapabilityTier.TIER_2_STANDARD
    return ModelCapabilityTier.TIER_2_STANDARD


def infer_tool_tier(tool_id: str) -> ModelCapabilityTier:
    return infer_model_capability_tier(tool_id)


def normalize_tool_name(name: object) -> InteractionKind:
    normalized = str(name).strip().lower()
    if not normalized:
        return InteractionKind.MISC
    if "mcp" in normalized:
        return InteractionKind.EXTERNAL
    if any(
        token in normalized
        for token in ("web_search", "web_fetch", "brave_search", "internet")
    ):
        return InteractionKind.BROWSE
    if normalized in {"read", "grep", "glob", "glob_file_search", "list_dir", "file_search"}:
        return InteractionKind.INSPECT
    if any(
        token in normalized
        for token in (
            "write",
            "edit",
            "multiedit",
            "notebookedit",
            "apply_patch",
            "apply_diff",
            "search_replace",
            "strreplace",
        )
    ):
        return InteractionKind.MODIFY
    if normalized in {"bash", "run_terminal_cmd", "execute", "shell"}:
        return InteractionKind.EXECUTE
    if "task" in normalized or "subagent" in normalized:
        return InteractionKind.DELEGATE
    if "skill" in normalized or normalized.startswith("/"):
        return InteractionKind.WORKFLOW
    if any(token in normalized for token in ("todo", "plan", "todowrite")):
        return InteractionKind.ORGANIZE
    if any(token in normalized for token in ("pytest", "jest", "vitest", "mocha", "cargo test", "go test")):
        return InteractionKind.VALIDATE
    if "git" in normalized:
        return InteractionKind.VERSION
    if "compact" in normalized:
        return InteractionKind.CONTEXT_CTRL
    return InteractionKind.MISC


def compute_tier_counts(tool_counts: dict[str, int]) -> dict[str, int]:
    acc: Counter[str] = Counter()
    for raw_name, count in tool_counts.items():
        kind = normalize_tool_name(raw_name)
        acc[str(kind.value)] += count
    return dict(acc)
