from ai_growth_mirror.domain.growth import costs


def test_estimate_cost_nonzero():
    v = costs.estimate_cost(1000, 1000, models_used=["gpt-4.1"])
    assert v is not None and v > 0
