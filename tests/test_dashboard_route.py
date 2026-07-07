from datetime import datetime

from fastapi.testclient import TestClient

from app.api.routes_dashboard import get_overview_provider
from app.main import app
from app.overview.summary_provider import EmptySummaryProvider


def test_dashboard_summary_supports_provider_override():
    app.dependency_overrides[get_overview_provider] = EmptySummaryProvider
    try:
        response = TestClient(app).get("/api/v1/dashboard/summary")
    finally:
        app.dependency_overrides.pop(get_overview_provider, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "NO_STORE"
    assert payload["totals"] == {
        "watchlist": 0,
        "setups": 0,
        "flow": 0,
        "plans": 0,
        "lifecycle": 0,
        "deliveries": 0,
    }
    assert payload["notes"] == ["No persistence provider is configured."]
    assert datetime.fromisoformat(payload["generated_at"]).tzinfo is not None
