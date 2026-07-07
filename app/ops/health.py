from asyncio import gather, timeout
from collections.abc import Awaitable, Callable, Mapping
from datetime import datetime
from time import perf_counter

from redis.asyncio import Redis
from sqlalchemy import text

from app.db.session import Database
from app.ops.models import DependencyCheck, OperationalHealth, OperationalState


Probe = Callable[[], Awaitable[None]]


def _require_aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("checked_at must be timezone-aware")


async def run_probe(
    name: str,
    probe: Probe,
    *,
    timeout_seconds: float = 2.0,
) -> DependencyCheck:
    normalized_name = name.strip()
    if not normalized_name:
        raise ValueError("probe name is required")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")

    started = perf_counter()
    try:
        async with timeout(timeout_seconds):
            await probe()
    except TimeoutError:
        state = OperationalState.DOWN
        detail = "timeout"
    except Exception as error:
        state = OperationalState.DOWN
        detail = type(error).__name__
    else:
        state = OperationalState.OK
        detail = ""

    return DependencyCheck(
        name=normalized_name,
        state=state,
        latency_ms=(perf_counter() - started) * 1000,
        detail=detail,
    )


def aggregate_state(checks: tuple[DependencyCheck, ...]) -> OperationalState:
    if not checks:
        return OperationalState.DEGRADED
    if all(check.state == OperationalState.OK for check in checks):
        return OperationalState.OK
    if all(check.state == OperationalState.DOWN for check in checks):
        return OperationalState.DOWN
    return OperationalState.DEGRADED


async def collect_health(
    probes: Mapping[str, Probe],
    *,
    checked_at: datetime,
    timeout_seconds: float = 2.0,
) -> OperationalHealth:
    _require_aware(checked_at)
    checks = tuple(
        await gather(
            *(
                run_probe(name, probe, timeout_seconds=timeout_seconds)
                for name, probe in probes.items()
            )
        )
    )
    return OperationalHealth(
        checked_at=checked_at,
        state=aggregate_state(checks),
        checks=checks,
    )


async def probe_database(url: str) -> None:
    database = Database(url)
    try:
        async with database.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    finally:
        await database.dispose()


async def probe_redis(url: str) -> None:
    client = Redis.from_url(url)
    try:
        await client.ping()
    finally:
        await client.aclose()


async def collect_default_health(
    *,
    database_url: str,
    redis_url: str,
    checked_at: datetime,
    timeout_seconds: float = 2.0,
) -> OperationalHealth:
    return await collect_health(
        {
            "database": lambda: probe_database(database_url),
            "redis": lambda: probe_redis(redis_url),
        },
        checked_at=checked_at,
        timeout_seconds=timeout_seconds,
    )
