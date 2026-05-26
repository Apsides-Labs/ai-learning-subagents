"""CostTracker + DataForSEOBudgetExceeded unit tests."""

import pytest


def test_cost_tracker_starts_at_zero():
    from services.dataforseo_client import CostTracker

    t = CostTracker(max_cost=1.0, max_calls=50)
    assert t.total_cost == 0.0
    assert t.total_calls == 0


def test_cost_tracker_records_calls():
    from services.dataforseo_client import CostTracker

    t = CostTracker(max_cost=1.0, max_calls=50)
    t.record(cost=0.002, endpoint="serp")
    t.record(cost=0.01, endpoint="kw_suggestions")

    assert t.total_calls == 2
    assert t.total_cost == pytest.approx(0.012)


def test_cost_tracker_raises_on_cost_cap():
    from services.dataforseo_client import CostTracker, DataForSEOBudgetExceeded

    t = CostTracker(max_cost=0.005, max_calls=50)
    t.record(cost=0.003, endpoint="a")
    with pytest.raises(DataForSEOBudgetExceeded) as exc:
        t.record(cost=0.003, endpoint="b")  # would cross the $0.005 cap

    assert "cost" in str(exc.value).lower()


def test_cost_tracker_raises_on_call_cap():
    from services.dataforseo_client import CostTracker, DataForSEOBudgetExceeded

    t = CostTracker(max_cost=10.0, max_calls=2)
    t.record(cost=0.0, endpoint="a")
    t.record(cost=0.0, endpoint="b")
    with pytest.raises(DataForSEOBudgetExceeded) as exc:
        t.record(cost=0.0, endpoint="c")

    assert "call" in str(exc.value).lower()


def test_cost_tracker_message_includes_recent_endpoints():
    """When the cap fires, the error should help debugging by naming recent endpoints."""
    from services.dataforseo_client import CostTracker, DataForSEOBudgetExceeded

    t = CostTracker(max_cost=10.0, max_calls=2)
    t.record(cost=0.0, endpoint="serp")
    t.record(cost=0.0, endpoint="kw_volume")
    with pytest.raises(DataForSEOBudgetExceeded) as exc:
        t.record(cost=0.0, endpoint="kw_difficulty")

    msg = str(exc.value)
    assert "serp" in msg and "kw_volume" in msg
