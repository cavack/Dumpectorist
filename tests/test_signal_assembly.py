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
from app.execution.symbol_mapping import CrossExchangeSymbolMap
from app.lifecycle.models import LifecycleState
from app.planning.models import PlanRequest, PlanStatus
from app.signals.models import (
    GateState,
    HigherTimeframeEvidenceOrigin,
    HigherTimeframeStructureEvidence,
    ShortSetupType,
    SignalAssemblyRequest,
    SignalAssemblyStatus,
)
from app.signals.service import assemble_signal
from app.structure.models import StructureInput


NOW = datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)


def make_lbank(*, mid: Decimal = Decimal("100"), spread: Decimal = Decimal("0.02")):
    half = spread / Decimal("2")
    bid = mid - half
    ask = mid + half
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
        received_at=NOW,
        latency_ms=100,
        instrument=instrument,
        quote=quote,
        order_book=book,
        spread=spread,
        spread_bps=(spread / mid) * Decimal("10000"),
        bid_depth_quote=Decimal("5000"),
        ask_depth_quote=Decimal("5000"),
    )


def exchange_symbol(source: BenchmarkSource) -> str:
    return "BTC_USDT" if source in {BenchmarkSource.MEXC, BenchmarkSource.GATE} else "BTCUSDT"


def make_benchmark(
    source: BenchmarkSource,
    price: Decimal,
    *,
    source_timestamp: datetime = NOW,
):
    bid = price - Decimal("0.01")
    ask = price + Decimal("0.01")
    spread = ask - bid
    return BenchmarkSnapshot(
        source=source,
        role=BenchmarkRole.BENCHMARK_ONLY,
        symbol=exchange_symbol(source),
        received_at=NOW,
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


def symbol_map() -> CrossExchangeSymbolMap:
    return CrossExchangeSymbolMap(
        canonical_symbol="BTCUSDT.P",
        lbank_symbol="BTCUSDT",
        benchmark_symbols={
            BenchmarkSource.MEXC: "BTC_USDT",
            BenchmarkSource.GATE: "BTC_USDT",
            BenchmarkSource.BYBIT: "BTCUSDT",
            BenchmarkSource.BINANCE: "BTCUSDT",
        },
    )


def make_request(
    *,
    daily: bool = True,
    four_hour: bool = True,
    lbank_mid: Decimal = Decimal("100"),
    lbank_spread: Decimal = Decimal("0.02"),
    current_value: float = 90,
    entry: float = 100,
    boundary: float = 101,
    benchmarks: tuple[BenchmarkSnapshot, ...] | None = None,
    plan_symbol: str = "BTCUSDT.P",
):
    return SignalAssemblyRequest(
        symbol="BTCUSDT.P",
        setup_type=ShortSetupType.FAILED_PULLBACK_SHORT,
        higher_timeframe=HigherTimeframeStructureEvidence(
            symbol="BTCUSDT.P",
            market_symbol="BTCUSDT",
            observed_at=NOW,
            daily_damaged=daily,
            four_hour_damaged=four_hour,
            origin=HigherTimeframeEvidenceOrigin.DERIVED,
            daily_zone_id="daily-zone",
            daily_event_id="daily-break" if daily else None,
            four_hour_zone_id="four-hour-zone",
            four_hour_event_id="four-hour-break" if four_hour else None,
            reasons=("derived structure evidence",),
        ),
        structure_input=StructureInput(
            symbol="BTCUSDT.P",
            current_value=current_value,
            reference_low=95,
            reference_high=105,
        ),
        lbank_snapshot=make_lbank(mid=lbank_mid, spread=lbank_spread),
        benchmark_snapshots=benchmarks
        or (
            make_benchmark(BenchmarkSource.MEXC, Decimal("99.9")),
            make_benchmark(BenchmarkSource.GATE, Decimal("100")),
            make_benchmark(BenchmarkSource.BYBIT, Decimal("100.1")),
            make_benchmark(BenchmarkSource.BINANCE, Decimal("100")),
        ),
        symbol_map=symbol_map(),
        plan_request=PlanRequest(
            symbol=plan_symbol,
            entry_value=entry,
            boundary_value=boundary,
            multiplier=4,
            ratio=2,
        ),
    )


def gate(report, name: str):
    return next(item for item in report.gates if item.name == name)


def test_happy_path_reaches_short_ready_without_discovery_records():
    report = assemble_signal(make_request(), now=NOW)

    assert report.status == SignalAssemblyStatus.SHORT_READY
    assert report.is_short_ready is True
    assert report.plan.status == PlanStatus.READY
    assert report.plan.objective_value == 98
    assert report.lifecycle.state == LifecycleState.ACTIVE
    assert gate(report, "discovery_context").state == GateState.WARN
    assert gate(report, "higher_timeframe_structure").state == GateState.PASS
    assert gate(report, "cross_exchange_consensus").passed is True
    assert gate(report, "lifecycle").state == GateState.PASS


def test_missing_four_hour_damage_stays_breakdown_watch():
    report = assemble_signal(make_request(four_hour=False), now=NOW)

    assert report.status == SignalAssemblyStatus.BREAKDOWN_WATCH
    assert report.plan.status == PlanStatus.HOLD
    assert report.lifecycle.state == LifecycleState.PENDING
    assert "FOUR_HOUR_STRUCTURE_NOT_DAMAGED" in gate(
        report, "higher_timeframe_structure"
    ).reasons
    assert gate(report, "lbank_execution").state == GateState.SKIP


def test_weak_lower_timeframe_structure_stays_weakness_watch():
    report = assemble_signal(make_request(current_value=97), now=NOW)

    assert report.status == SignalAssemblyStatus.WEAKNESS_WATCH
    assert report.plan.status == PlanStatus.HOLD
    assert gate(report, "flow").state == GateState.FAIL
    assert gate(report, "lbank_execution").state == GateState.SKIP


def test_wide_lbank_spread_returns_execution_pending():
    report = assemble_signal(make_request(lbank_spread=Decimal("0.30")), now=NOW)

    assert report.status == SignalAssemblyStatus.EXECUTION_PENDING
    assert report.plan.status == PlanStatus.HOLD
    assert "SPREAD_TOO_WIDE" in gate(report, "lbank_execution").reasons
    assert gate(report, "cross_exchange_consensus").state == GateState.SKIP


def test_stale_benchmarks_return_data_degraded():
    stale = NOW - timedelta(seconds=21)
    benchmarks = (
        make_benchmark(BenchmarkSource.BINANCE, Decimal("100"), source_timestamp=stale),
        make_benchmark(BenchmarkSource.BYBIT, Decimal("100"), source_timestamp=stale),
    )

    report = assemble_signal(make_request(benchmarks=benchmarks), now=NOW)

    assert report.status == SignalAssemblyStatus.DATA_DEGRADED
    assert "INSUFFICIENT_FRESH_BENCHMARK_SOURCES" in gate(
        report, "cross_exchange_consensus"
    ).reasons


def test_large_cross_exchange_deviation_returns_avoid():
    report = assemble_signal(
        make_request(lbank_mid=Decimal("101.1"), entry=101.1, boundary=102.1),
        now=NOW,
    )

    assert report.status == SignalAssemblyStatus.AVOID
    assert report.plan.status == PlanStatus.HOLD
    assert "LBANK_DEVIATION_AVOID" in gate(
        report, "cross_exchange_consensus"
    ).reasons


def test_entry_too_far_from_lbank_stays_execution_pending():
    report = assemble_signal(make_request(entry=100.6, boundary=101.6), now=NOW)

    assert report.status == SignalAssemblyStatus.EXECUTION_PENDING
    assert report.entry_deviation_bps == Decimal("60.0")
    assert "ENTRY_TOO_FAR_FROM_LBANK" in gate(report, "entry_alignment").reasons
    assert gate(report, "planning").state == GateState.SKIP


def test_invalid_plan_is_reported_without_short_ready():
    report = assemble_signal(make_request(entry=100, boundary=99), now=NOW)

    assert report.status == SignalAssemblyStatus.DATA_DEGRADED
    assert report.plan.status == PlanStatus.HOLD
    assert gate(report, "planning").state == GateState.FAIL
    assert any("ValueError" in reason for reason in gate(report, "planning").reasons)


def test_plan_symbol_mismatch_blocks_before_market_gates():
    report = assemble_signal(make_request(plan_symbol="ETHUSDT.P"), now=NOW)

    assert report.status == SignalAssemblyStatus.DATA_DEGRADED
    assert "PLAN_SYMBOL_MISMATCH" in gate(report, "symbol_alignment").reasons
    assert gate(report, "higher_timeframe_structure").state == GateState.SKIP


def test_manual_higher_timeframe_evidence_is_rejected():
    with pytest.raises(ValueError, match="derived higher-timeframe evidence"):
        HigherTimeframeStructureEvidence(
            symbol="BTCUSDT.P",
            market_symbol="BTCUSDT",
            observed_at=NOW,
            daily_damaged=True,
            four_hour_damaged=True,
            origin=HigherTimeframeEvidenceOrigin.MANUAL,
        )


def test_naive_now_is_rejected():
    with pytest.raises(ValueError):
        assemble_signal(make_request(), now=datetime(2026, 7, 7, 12, 0))
