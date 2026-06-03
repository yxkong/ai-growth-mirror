"""Mini-chart geometry for growth trajectory axis series."""

from __future__ import annotations

from ai_growth_mirror.application.growth_trajectory import _chart_points, _series_view


def test_chart_points_mini_height_for_axis_trends():
    full_coords, _ = _chart_points([10.0, 20.0, 30.0], chart_height=112.0)
    mini_coords, _ = _chart_points([10.0, 20.0, 30.0], chart_height=64.0)
    assert full_coords
    assert mini_coords
    assert max(item["y"] for item in mini_coords) <= 64.0
    assert max(item["y"] for item in full_coords) <= 112.0


def test_series_view_axis_mode_uses_mini_chart_height():
    class _Point:
        snapshot_id = "snap-1"
        date = "2026-05-01"

    series = _series_view(
        key="intent_clarity",
        label="Intent",
        color="#2563eb",
        values=[40.0, 55.0, 60.0],
        points=[_Point(), _Point(), _Point()],
        value_mode="axis",
    )
    assert series.area_path
    assert all(point["y"] <= 64.0 for point in series.points)
