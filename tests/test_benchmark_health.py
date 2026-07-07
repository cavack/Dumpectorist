from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.adapters.benchmark_health import (
    BenchmarkHealthRules,
    BenchmarkHealthState,
    evaluate_benchmark_health,
)
from app.adapters.benchmark_models import (
    BenchmarkRole,
    BenchmarkSnapshot,
    BenchmarkSource,
)


NOW = datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)


def snapshot(
    *,
    received_at: datetime = NOW,
    source_timestamp: datetime | None = NOW,
    latency_ms: int = 100,
) -> BenchmarkSnapshot:
    return BenchmarkSnapshot(
        source=BenchmarkSource.BINANCE,
        role=BenchmarkRole.BENCHMARK_ONLY,
        symbol="BTCUSDT",
        received_at=received_at,
        latency_ms=latency_ms,
        source_timestamp=source_timestamp,
        last_price=Decimal("60000"),
        mark_price=Decimal("60001"),
        index_price=Decimal("59999"),
        funding_rate=Decimal("0.0001"),
        open_interest=Decimal("12345"),
        best_bid=Decimal("59999"),
        best_ask=Decimal("60001"),
        spread=Decimal("2"),
        spread_bps=Decimal("0.3333"),
        bid_depth_quote=Decimal("10000"),
        ask_depth_quote=Decimal("10000"),
    )


def test_fresh_benchmark_is_usable():
    report = evaluate_benchmark_health(snapshot(), now=NOW)

    assert report.state == BenchmarkHealthState.OK
    assert report.is_usable is True
    assert report.reasons == ()


def test_missing_source_timestamp_is_degraded():
    report = evaluate_benchmark_health(snapshot(source_timestamp=None), now=NOW)

    assert report.state == BenchmarkHealthState.DEGRADED
    assert report.is_usable is False
    assert report.reasons == ("SOURCE_TIMESTAMP_MISSING",)


def test_stale_source_timestamp_has_priority():
    report = evaluate_benchmark_health(
        snapshot(
            source_timestamp=NOW - timedelta(seconds=21),
            latency_ms=3000,
        ),
        now=NOW,
    )

    assert report.state == BenchmarkHealthState.STALE
    assert report.reasons == ("SOURCE_TIME_STALE", "SOURCE_LATENCY_HIGH")


def test_stale_receive_time_is_reported():
    report = evaluate_benchmark_health(
        snapshot(received_at=NOW - timedelta(seconds=11)),
        now=NOW,
    )

    assert report.state == BenchmarkHealthState.STALE
    assert report.reasons == ("RECEIVE_TIME_STALE",)


def test_health_requires_aware_now_and_valid_rules():
    with pytest.raises(ValueError):
        evaluate_benchmark_health(
            snapshot(),
            now=datetime(2026, 7, 7, 12, 0),
        )
    with pytest.raises(ValueError):
        BenchmarkHealthRules(max_latency_ms=0)
