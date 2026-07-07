from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

from app.adapters.benchmark_models import BenchmarkSource
from app.execution.consensus import ConsensusRules
from app.execution.liquidity_models import ExecutionReadiness, OrderSide
from app.execution.order_constraints import ExecutionOrderRequest
from app.execution.readiness import evaluate_readiness
from app.execution.symbol_mapping import CrossExchangeSymbolMap
from tests.test_consensus import make_benchmark
from tests.test_liquidity import NOW, snapshot


def mapping():
    return CrossExchangeSymbolMap(
        canonical_symbol="BTCUSDT.P",
        lbank_symbol="BTC_USDT",
        benchmark_symbols={
            BenchmarkSource.MEXC: "BTC_USDT",
            BenchmarkSource.GATE: "BTC_USDT",
            BenchmarkSource.BYBIT: "BTCUSDT",
            BenchmarkSource.BINANCE: "BTCUSDT",
        },
    )


def benchmarks():
    return (
        make_benchmark(BenchmarkSource.MEXC, Decimal("99.95")),
        make_benchmark(BenchmarkSource.GATE, Decimal("100.00")),
        make_benchmark(BenchmarkSource.BYBIT, Decimal("100.05")),
        make_benchmark(BenchmarkSource.BINANCE, Decimal("100.00")),
    )


def request():
    return ExecutionOrderRequest(
        side=OrderSide.SELL,
        price=Decimal("100.0"),
        volume=Decimal("1.000"),
        post_only=True,
    )


def test_aligned_sources_allow_executable_readiness():
    report = evaluate_readiness(
        lbank_snapshot=snapshot(scale="5"),
        benchmark_snapshots=benchmarks(),
        symbol_map=mapping(),
        now=NOW,
        contract_active=True,
        order_request=request(),
    )

    assert report.readiness == ExecutionReadiness.EXECUTABLE
    assert report.executable is True
    assert report.consensus.usable_sources == 4
    assert all(item.included for item in report.source_clocks)


def test_clock_outlier_is_excluded_but_enough_sources_remain():
    items = list(benchmarks())
    items[0] = replace(
        items[0],
        source_timestamp=NOW - timedelta(seconds=30),
        received_at=NOW,
    )
    report = evaluate_readiness(
        lbank_snapshot=snapshot(scale="5"),
        benchmark_snapshots=tuple(items),
        symbol_map=mapping(),
        now=NOW,
        contract_active=True,
        order_request=request(),
        max_source_clock_delta_seconds=10,
    )

    assert report.readiness == ExecutionReadiness.EXECUTABLE
    excluded = next(item for item in report.source_clocks if not item.included)
    assert excluded.reasons == ("SOURCE_TIMESTAMP_DELTA_TOO_HIGH",)
    assert "BENCHMARK_TIMESTAMP_ALIGNMENT_EXCLUSIONS" in report.warnings
    assert report.consensus.usable_sources == 3


def test_clock_exclusions_trigger_minimum_source_gate():
    items = tuple(
        replace(item, source_timestamp=NOW - timedelta(seconds=30))
        for item in benchmarks()[:3]
    ) + (benchmarks()[3],)
    report = evaluate_readiness(
        lbank_snapshot=snapshot(scale="5"),
        benchmark_snapshots=items,
        symbol_map=mapping(),
        now=NOW,
        contract_active=True,
        order_request=request(),
        max_source_clock_delta_seconds=10,
        consensus_rules=ConsensusRules(minimum_fresh_sources=2),
    )

    assert report.readiness == ExecutionReadiness.DATA_DEGRADED
    assert "INSUFFICIENT_FRESH_BENCHMARK_SOURCES" in report.reasons


def test_unreliable_symbol_mapping_is_degraded():
    unreliable = replace(mapping(), reliable=False)
    report = evaluate_readiness(
        lbank_snapshot=snapshot(scale="5"),
        benchmark_snapshots=benchmarks(),
        symbol_map=unreliable,
        now=NOW,
        contract_active=True,
        order_request=request(),
    )

    assert report.readiness == ExecutionReadiness.DATA_DEGRADED
    assert "SYMBOL_MAPPING_UNRELIABLE" in report.reasons


def test_large_lbank_deviation_is_no_trade():
    shifted = replace(
        snapshot(scale="5"),
        quote=replace(
            snapshot(scale="5").quote,
            last_price=Decimal("102"),
            marked_price=Decimal("102"),
        ),
    )
    report = evaluate_readiness(
        lbank_snapshot=shifted,
        benchmark_snapshots=benchmarks(),
        symbol_map=mapping(),
        now=NOW,
        contract_active=True,
        order_request=request(),
    )

    assert report.readiness == ExecutionReadiness.NO_TRADE
    assert "LBANK_DEVIATION_AVOID" in report.reasons
