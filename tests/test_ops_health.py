from asyncio import sleep
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.api.routes_operations import get_operational_health
from app.main import app
from app.ops.health import collect_health, probe_database
from app.ops.models import DependencyCheck, OperationalHealth, OperationalState


NOW = datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)


async def ok_probe() -> None:
    return None


async def failed_probe() -> None:
    raise RuntimeError("unavailable")


async def slow_probe() -> None:
    await sleep(0.05)


@pytest.mark.asyncio
async def test_health_is_degraded_when_one_dependency_is_down():
    health = await collect_health(
        {"database": ok_probe, "redis": failed_probe},
        checked_at=NOW,
    )

    assert health.state == OperationalState.DEGRADED
    assert health.checks[0].state == OperationalState.OK
    assert health.checks[1].state == OperationalState.DOWN
    assert health.checks[1].detail == "RuntimeError"


@pytest.mark.asyncio
async def test_health_is_down_when_all_dependencies_are_down():
    health = await collect_health(
        {"database": failed_probe, "redis": failed_probe},
        checked_at=NOW,
    )

    assert health.state == OperationalState.DOWN


@pytest.mark.asyncio
async def test_probe_timeout_is_reported_as_down():
    health = await collect_health(
        {"slow": slow_probe},
        checked_at=NOW,
        timeout_seconds=0.001,
    )

    assert health.state == OperationalState.DOWN
    assert health.checks[0].detail == "timeout"


@pytest.mark.asyncio
async def test_database_probe_supports_async_sqlite():
    await probe_database("sqlite+aiosqlite:///:memory:")


@pytest.mark.asyncio
async def test_health_rejects_naive_timestamp():
    with pytest.raises(ValueError):
        await collect_health(
            {"database": ok_probe},
            checked_at=datetime(2026, 7, 7, 12, 0),
        )


def test_operational_health_route_uses_dependency_result():
    expected = OperationalHealth(
        checked_at=NOW,
        state=OperationalState.DEGRADED,
        checks=(
            DependencyCheck(
                name="database",
                state=OperationalState.OK,
                latency_ms=1.0,
            ),
            DependencyCheck(
                name="redis",
                state=OperationalState.DOWN,
                latency_ms=2.0,
                detail="timeout",
            ),
        ),
    )

    async def override_health() -> OperationalHealth:
        return expected

    app.dependency_overrides[get_operational_health] = override_health
    try:
        response = TestClient(app).get("/api/v1/health/operations")
    finally:
        app.dependency_overrides.pop(get_operational_health, None)

    assert response.status_code == 200
    payload = response.json()
    assert payload["state"] == "DEGRADED"
    assert payload["checks"][1]["detail"] == "timeout"
