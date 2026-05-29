from ai_growth_mirror.domain.growth.model import GrowthProfile
from ai_growth_mirror.application.growth_plan import build_growth_plan
from tests.conftest import load_report_label_catalogs


def test_growth_plan_falls_back_to_consolidation_when_no_gaps():
    stats = GrowthProfile(
        tool_name="codex",
        pq_avg_dimensions={},
        friction_by_attribution={"user-actionable": 0, "ai-capability": 0, "environmental": 0},
    )

    plan = build_growth_plan(
        stats=stats,
        capability_scores={
            "intent_clarity": 72,
            "execution_driving": 70,
            "implementation_depth": 66,
            "delivery_closure": 74,
            "adaptive_recovery": 68,
        },
        catalogs=load_report_label_catalogs("en"),
    )

    assert plan.priorities[0].key == "consolidation"
    assert plan.next_focus == plan.priorities[0].title


def test_growth_plan_prefers_lowest_prompt_dimension_before_capability_gaps():
    stats = GrowthProfile(
        tool_name="codex",
        pq_avg_dimensions={
            "context_provision": 62.0,
            "request_specificity": 41.0,
            "scope_management": 58.0,
        },
        friction_by_attribution={"user-actionable": 0, "ai-capability": 1, "environmental": 1},
    )

    plan = build_growth_plan(
        stats=stats,
        capability_scores={
            "intent_clarity": 64,
            "execution_driving": 52,
            "implementation_depth": 49,
            "delivery_closure": 40,
            "adaptive_recovery": 30,
        },
        catalogs=load_report_label_catalogs("zh"),
    )

    assert plan.priorities
    assert plan.priorities[0].key == "prompt:request_specificity"
    assert plan.priorities[0].practice_prompt


def test_growth_plan_collapses_friction_and_correction_quality_into_one_track():
    stats = GrowthProfile(
        tool_name="codex",
        pq_avg_dimensions={
            "context_provision": 62.0,
            "request_specificity": 61.0,
            "scope_management": 59.0,
            "correction_quality": 32.0,
        },
        friction_by_attribution={"user-actionable": 4, "ai-capability": 0, "environmental": 0},
    )

    plan = build_growth_plan(
        stats=stats,
        capability_scores={
            "intent_clarity": 72,
            "execution_driving": 70,
            "implementation_depth": 66,
            "delivery_closure": 74,
            "adaptive_recovery": 60,
        },
        catalogs=load_report_label_catalogs("zh"),
    )

    keys = [item.key for item in plan.priorities]
    assert any(key in {"friction", "prompt:correction_quality"} for key in keys)
    assert not (
        "friction" in keys and "prompt:correction_quality" in keys
    )
