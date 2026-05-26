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


import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_get_client_returns_singleton():
    """Two calls return the same instance — required for the cost cap to be process-scoped."""
    from services import dataforseo_client as mod
    mod._client = None  # reset for test isolation

    with patch.object(mod, "settings") as mock_settings:
        mock_settings.dataforseo_login = "user@example.com"
        mock_settings.dataforseo_password = "pass"
        mock_settings.dataforseo_max_cost_per_run = 1.0
        mock_settings.dataforseo_max_calls_per_run = 50

        a = mod.get_client()
        b = mod.get_client()
        assert a is b


async def test_post_records_cost_from_response():
    from services import dataforseo_client as mod
    mod._client = None

    response_json = _load_fixture("dfs_serp_response.json")
    mock_response = MagicMock()
    mock_response.json = MagicMock(return_value=response_json)
    mock_response.raise_for_status = MagicMock()

    with patch.object(mod, "settings") as mock_settings:
        mock_settings.dataforseo_login = "user@example.com"
        mock_settings.dataforseo_password = "pass"
        mock_settings.dataforseo_max_cost_per_run = 1.0
        mock_settings.dataforseo_max_calls_per_run = 50

        client = mod.get_client()
        client._http = MagicMock()
        client._http.post = AsyncMock(return_value=mock_response)

        result = await client.post("/v3/serp/google/organic/live/advanced", json_body=[{"keyword": "x"}])

        assert client.tracker.total_calls == 1
        assert client.tracker.total_cost == pytest.approx(0.002)
        assert result == response_json
