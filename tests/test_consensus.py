from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.adapters.benchmark_models import (
    BenchmarkRole,
    BenchmarkSnapshot,
    BenchmarkSource,
)
from app.adapters.lbank_models import (
    LBankBookLevel,
    LBankExecutionSnapshot,
    LBankInstrument,
    LBankMarketQuote,
    LBankOrderBook,
)
from app.execution.consensus import (
    ConsensusRules,
    ConsensusStatus,
    build_cross_exchange_consensus,
)
from app.execution.symbol_mapping import CrossExchangeSymbolMap


NOW = datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)


def make_lbank(
    *,
    mid: Decimal = Decimal("100"),
    spread: Decimal = Decimal("0.02"),
    received_at: datetime = NOW,
) -> LBankExecutionSnapshot:
    half = spread / Decimal("2")
    bid = mid - half
    ask = mid + half
    spread_bps = (spread / mid) * Decimal("10000")
    instrument = LBankInstrument(
        symbol="BTCUSDT",
        base_currency="BTC",
        price_currency="USDT",
        clear_currency="USDT",
        price_tick=Decimal("0.01"),
        volume_tick=Decimal("1"),
        volume_multiple=Decimal("0.001"),
        min_order_volume=Decimal("1"),
        min_order_cost=Decimal("5"),
    )
    quote = LBankMarketQuote(
        symbol="BTCUSDT",
        last_price=mid,
        marked_price=mid,
        funding_rate=Decimal("0.0001"),
        volume_24h=Decimal("100000"),
        turnover_24h=Decimal("10000000"),
    )
    book = LBankOrderBook(
        symbol="BTCUSDT",
        bids=(LBankBookLevel(price=bid, volume=Decimal("100")),),
        asks=(LBankBookLevel(price=ask, volume=Decimal("100")),),
    )
    return LBankExecutionSnapshot(
        source="LBank",
        product_group="SwapU",
        symbol="BTCUSDT",
        received_at=received_at,
        latency_ms=100,
        instrument=instrument,
        quote=quote,
        order_book=book,
        spread=spread,
        spread_bps=spread_bps,
        bid_depth_quote=Decimal("5000"),
        ask_depth_quote=Decimal("5000"),
    )


def source_symbol(source: BenchmarkSource) -> str:
    if source in {BenchmarkSource.MEXC, BenchmarkSource.GATE}:
        return "BTC_USDT"
    return "BTCUSDT"


def make_benchmark(
    source: BenchmarkSource,
    price: Decimal,
    *,
    symbol: str | None = None,
    source_timestamp: datetime | None = NOW,
    received_at: datetime = NOW,
) -> BenchmarkSnapshot:
    bid = price - Decimal("0.01")
    ask = price + Decimal("0.01")
    spread = ask - bid
    return BenchmarkSnapshot(
        source=source,
        role=BenchmarkRole.BENCHMARK_ONLY,
        symbol=symbol or source_symbol(source),
        received_at=received_at,
        latency_ms=100,
        source_timestamp=source_timestamp,
        last_price=price,
        mark_price=price,
        index_price=price,
        funding_rate=Decimal("0.0001"),
        open_interest=Decimal("10000"),
        best_bid=bid,
        best_ask=ask,
        spread=spread,
        spread_bps=(spread / price) * Decimal("10000"),
        bid_depth_quote=Decimal("10000"),
        ask_depth_quote=Decimal("10000"),
    )


def symbol_map(*, reliable: bool = True) -> CrossExchangeSymbolMap:
    return CrossExchangeSymbolMap(
        canonical_symbol="BTCUSDT.P",
        lbank_symbol="BTCUSDT",
        benchmark_symbols={
            BenchmarkSource.MEXC: "BTC_USDT",
            BenchmarkSource.GATE: "BTC_USDT",
            BenchmarkSource.BYBIT: "BTCUSDT",
            BenchmarkSource.BINANCE: "BTCUSDT",
        },
        reliable=reliable,
    )


def benchmarks_around_100() -> tuple[BenchmarkSnapshot, ...]:
    return (
        make_benchmark(BenchmarkSource.MEXC, Decimal("99.90")),
        make_benchmark(BenchmarkSource.GATE, Decimal("100.00")),
        make_benchmark(BenchmarkSource.BYBIT, Decimal("100.10")),
        make_benchmark(BenchmarkSource.BINANCE, Decimal("100.00")),
    )


def test_consensus_is_ok_with_fresh_tight_sources():
    report = build_cross_exchange_consensus(
        lbank_snapshot=make_lbank(),
        benchmark_snapshots=benchmarks_around_100(),
        symbol_map=symbol_map(),
        now=NOW,
    )

    assert report.status == ConsensusStatus.OK
    assert report.allows_execution_confirmation is True
    assert report.median_benchmark_price == Decimal("100.00")
    assert report.lbank_deviation_pct == Decimal("0")
    assert report.usable_sources == 4
    assert all(result.included for result in report.source_results)


@pytest.mark.parametrize(
    ("lbank_mid", "expected_status", "expected_reason"),
    [
        (Decimal("100.30"), ConsensusStatus.WARNING, "LBANK_DEVIATION_WARNING"),
        (
            Decimal("100.60"),
            ConsensusStatus.DATA_DEGRADED,
            "LBANK_DEVIATION_DEGRADED",
        ),
        (Decimal("101.10"), ConsensusStatus.AVOID, "LBANK_DEVIATION_AVOID"),
    ],
)
def test_lbank_deviation_thresholds(
    lbank_mid: Decimal,
    expected_status: ConsensusStatus,
    expected_reason: str,
):
    report = build_cross_exchange_consensus(
        lbank_snapshot=make_lbank(mid=lbank_mid),
        benchmark_snapshots=benchmarks_around_100(),
        symbol_map=symbol_map(),
        now=NOW,
    )

    assert report.status == expected_status
    assert report.reasons == (expected_reason,)


def test_stale_source_is_excluded_and_minimum_is_enforced():
    snapshots = (
        make_benchmark(BenchmarkSource.BINANCE, Decimal("100")),
        make_benchmark(
            BenchmarkSource.BYBIT,
            Decimal("100"),
            source_timestamp=NOW - timedelta(seconds=21),
        ),
    )
    report = build_cross_exchange_consensus(
        lbank_snapshot=make_lbank(),
        benchmark_snapshots=snapshots,
        symbol_map=symbol_map(),
        now=NOW,
    )

    assert report.status == ConsensusStatus.DATA_DEGRADED
    assert report.usable_sources == 1
    assert report.reasons == ("INSUFFICIENT_FRESH_BENCHMARK_SOURCES",)
    stale = next(item for item in report.source_results if item.source == BenchmarkSource.BYBIT)
    assert stale.included is False
    assert stale.reasons == ("SOURCE_TIME_STALE",)


def test_high_benchmark_dispersion_degrades_consensus():
    snapshots = (
        make_benchmark(BenchmarkSource.BINANCE, Decimal("99")),
        make_benchmark(BenchmarkSource.BYBIT, Decimal("101")),
    )
    report = build_cross_exchange_consensus(
        lbank_snapshot=make_lbank(),
        benchmark_snapshots=snapshots,
        symbol_map=symbol_map(),
        now=NOW,
    )

    assert report.status == ConsensusStatus.DATA_DEGRADED
    assert report.benchmark_dispersion_pct == Decimal("2")
    assert report.reasons == ("BENCHMARK_DISPERSION_TOO_HIGH",)


def test_unreliable_symbol_mapping_blocks_consensus():
    report = build_cross_exchange_consensus(
        lbank_snapshot=make_lbank(),
        benchmark_snapshots=benchmarks_around_100(),
        symbol_map=symbol_map(reliable=False),
        now=NOW,
    )

    assert report.status == ConsensusStatus.DATA_DEGRADED
    assert report.usable_sources == 0
    assert report.median_benchmark_price is None
    assert report.reasons == ("SYMBOL_MAPPING_UNRELIABLE",)


def test_source_symbol_mismatch_is_excluded():
    snapshots = (
        make_benchmark(BenchmarkSource.BINANCE, Decimal("100"), symbol="ETHUSDT"),
        make_benchmark(BenchmarkSource.BYBIT, Decimal("100")),
    )
    report = build_cross_exchange_consensus(
        lbank_snapshot=make_lbank(),
        benchmark_snapshots=snapshots,
        symbol_map=symbol_map(),
        now=NOW,
    )

    assert report.status == ConsensusStatus.DATA_DEGRADED
    mismatch = next(
        item for item in report.source_results if item.source == BenchmarkSource.BINANCE
    )
    assert mismatch.included is False
    assert mismatch.reasons == ("SYMBOL_MISMATCH",)


def test_wide_lbank_spread_returns_execution_pending():
    report = build_cross_exchange_consensus(
        lbank_snapshot=make_lbank(spread=Decimal("0.30")),
        benchmark_snapshots=benchmarks_around_100(),
        symbol_map=symbol_map(),
        now=NOW,
    )

    assert report.status == ConsensusStatus.EXECUTION_PENDING
    assert report.allows_execution_confirmation is False
    assert report.reasons == ("SPREAD_TOO_WIDE",)


def test_duplicate_benchmark_source_is_not_counted_twice():
    snapshots = (
        make_benchmark(BenchmarkSource.BINANCE, Decimal("100")),
        make_benchmark(BenchmarkSource.BINANCE, Decimal("100.01")),
        make_benchmark(BenchmarkSource.BYBIT, Decimal("100")),
    )
    report = build_cross_exchange_consensus(
        lbank_snapshot=make_lbank(),
        benchmark_snapshots=snapshots,
        symbol_map=symbol_map(),
        now=NOW,
    )

    assert report.status == ConsensusStatus.OK
    assert report.usable_sources == 2
    duplicate = report.source_results[1]
    assert duplicate.included is False
    assert duplicate.reasons == ("DUPLICATE_SOURCE",)


def test_symbol_map_copies_input_and_rules_are_validated():
    symbols = {BenchmarkSource.BINANCE: "BTCUSDT"}
    mapping = CrossExchangeSymbolMap(
        canonical_symbol="BTCUSDT.P",
        lbank_symbol="BTCUSDT",
        benchmark_symbols=symbols,
    )
    symbols[BenchmarkSource.BINANCE] = "ETHUSDT"

    assert mapping.expected_symbol(BenchmarkSource.BINANCE) == "BTCUSDT"
    with pytest.raises(ValueError):
        ConsensusRules(
            warning_deviation_pct=Decimal("0.5"),
            degraded_deviation_pct=Decimal("0.4"),
        )
