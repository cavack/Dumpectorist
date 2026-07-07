from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.adapters.lbank_models import (
    LBankBookLevel,
    LBankExecutionSnapshot,
    LBankInstrument,
    LBankMarketQuote,
    LBankOrderBook,
)
from app.execution.lbank_validator import (
    LBankExecutionRules,
    LBankExecutionStatus,
    validate_lbank_execution,
)


NOW = datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)


def make_snapshot(
    *,
    received_at: datetime = NOW,
    latency_ms: int = 100,
    spread_bps: Decimal = Decimal("5"),
    bid_depth: Decimal = Decimal("5000"),
    ask_depth: Decimal = Decimal("5000"),
) -> LBankExecutionSnapshot:
    instrument = LBankInstrument(
        symbol="BTCUSDT",
        base_currency="BTC",
        price_currency="USDT",
        clear_currency="USDT",
        price_tick=Decimal("0.1"),
        volume_tick=Decimal("1"),
        volume_multiple=Decimal("0.001"),
        min_order_volume=Decimal("1"),
        min_order_cost=Decimal("5"),
    )
    quote = LBankMarketQuote(
        symbol="BTCUSDT",
        last_price=Decimal("60000"),
        marked_price=Decimal("60001"),
        funding_rate=Decimal("0.0001"),
        volume_24h=Decimal("250000"),
        turnover_24h=Decimal("15000000"),
    )
    order_book = LBankOrderBook(
        symbol="BTCUSDT",
        bids=(LBankBookLevel(price=Decimal("59999"), volume=Decimal("8")),),
        asks=(LBankBookLevel(price=Decimal("60002"), volume=Decimal("10")),),
    )
    return LBankExecutionSnapshot(
        source="LBank",
        product_group="SwapU",
        symbol="BTCUSDT",
        received_at=received_at,
        latency_ms=latency_ms,
        instrument=instrument,
        quote=quote,
        order_book=order_book,
        spread=Decimal("3"),
        spread_bps=spread_bps,
        bid_depth_quote=bid_depth,
        ask_depth_quote=ask_depth,
    )


def test_execution_is_ok_when_all_hard_gates_pass():
    result = validate_lbank_execution(make_snapshot(), now=NOW)

    assert result.status == LBankExecutionStatus.OK
    assert result.is_executable is True
    assert result.reasons == ()


def test_wide_spread_and_low_depth_wait_for_execution():
    result = validate_lbank_execution(
        make_snapshot(
            spread_bps=Decimal("30"),
            bid_depth=Decimal("500"),
            ask_depth=Decimal("400"),
        ),
        now=NOW,
    )

    assert result.status == LBankExecutionStatus.EXECUTION_PENDING
    assert result.is_executable is False
    assert result.reasons == (
        "SPREAD_TOO_WIDE",
        "BID_DEPTH_INSUFFICIENT",
        "ASK_DEPTH_INSUFFICIENT",
    )


def test_stale_snapshot_is_data_degraded():
    result = validate_lbank_execution(
        make_snapshot(received_at=NOW - timedelta(seconds=16)),
        now=NOW,
    )

    assert result.status == LBankExecutionStatus.DATA_DEGRADED
    assert result.reasons == ("SNAPSHOT_STALE",)


def test_high_source_latency_is_data_degraded():
    result = validate_lbank_execution(
        make_snapshot(latency_ms=2501),
        now=NOW,
    )

    assert result.status == LBankExecutionStatus.DATA_DEGRADED
    assert result.reasons == ("SOURCE_LATENCY_HIGH",)


def test_future_snapshot_is_data_degraded():
    result = validate_lbank_execution(
        make_snapshot(received_at=NOW + timedelta(seconds=2)),
        now=NOW,
    )

    assert result.status == LBankExecutionStatus.DATA_DEGRADED
    assert result.reasons == ("SNAPSHOT_FROM_FUTURE",)


def test_validator_requires_timezone_aware_now():
    with pytest.raises(ValueError):
        validate_lbank_execution(
            make_snapshot(),
            now=datetime(2026, 7, 7, 12, 0),
        )


def test_rules_reject_invalid_thresholds():
    with pytest.raises(ValueError):
        LBankExecutionRules(max_age_seconds=0)
    with pytest.raises(ValueError):
        LBankExecutionRules(max_spread_bps=Decimal("0"))
    with pytest.raises(ValueError):
        LBankExecutionRules(min_bid_depth_quote=Decimal("-1"))
