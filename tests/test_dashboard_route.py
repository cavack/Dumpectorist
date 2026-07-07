from datetime import datetime

from fastapi.testclient import TestClient

from app.main import app


def test_dashboard_summary_reports_empty_no_store_state():
    client = TestClient(app)

    response = client.get("/api/v1/dashboard/summary")

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
