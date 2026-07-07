from dataclasses import dataclass, field, replace
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from statistics import median

from app.adapters.benchmark_health import (
    BenchmarkHealthRules,
    BenchmarkHealthState,
    evaluate_benchmark_health,
)
from app.adapters.benchmark_models import BenchmarkSnapshot, BenchmarkSource
from app.adapters.lbank_models import LBankExecutionSnapshot
from app.execution.lbank_validator import (
    LBankExecutionRules,
    LBankExecutionStatus,
    validate_lbank_execution,
)
from app.execution.symbol_mapping import CrossExchangeSymbolMap


class ConsensusStatus(StrEnum):
    OK = "OK"
    WARNING = "WARNING"
    EXECUTION_PENDING = "EXECUTION_PENDING"
    DATA_DEGRADED = "DATA_DEGRADED"
    AVOID = "AVOID"


@dataclass(frozen=True)
class ConsensusRules:
    minimum_fresh_sources: int = 2
    warning_deviation_pct: Decimal = Decimal("0.20")
    degraded_deviation_pct: Decimal = Decimal("0.50")
    avoid_deviation_pct: Decimal = Decimal("1.00")
    max_benchmark_dispersion_pct: Decimal = Decimal("1.00")
    benchmark_health: BenchmarkHealthRules = field(default_factory=BenchmarkHealthRules)
    lbank_execution: LBankExecutionRules = field(default_factory=LBankExecutionRules)

    def __post_init__(self) -> None:
        if self.minimum_fresh_sources < 1:
            raise ValueError("minimum_fresh_sources must be positive")
        if not (
            Decimal("0")
            < self.warning_deviation_pct
            < self.degraded_deviation_pct
            < self.avoid_deviation_pct
        ):
            raise ValueError("deviation thresholds must be positive and increasing")
        if self.max_benchmark_dispersion_pct <= 0:
            raise ValueError("max_benchmark_dispersion_pct must be positive")


@dataclass(frozen=True)
class ConsensusSourceResult:
    source: BenchmarkSource
    exchange_symbol: str
    expected_symbol: str | None
    health_state: BenchmarkHealthState | None
    price: Decimal
    included: bool
    deviation_from_median_pct: Decimal | None = None
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class CrossExchangeConsensusReport:
    canonical_symbol: str
    lbank_symbol: str
    lbank_price: Decimal
    median_benchmark_price: Decimal | None
    lbank_deviation_pct: Decimal | None
    benchmark_dispersion_pct: Decimal | None
    status: ConsensusStatus
    usable_sources: int
    source_results: tuple[ConsensusSourceResult, ...]
    reasons: tuple[str, ...]

    @property
    def allows_execution_confirmation(self) -> bool:
        return self.status in {ConsensusStatus.OK, ConsensusStatus.WARNING}


def _deviation_pct(value: Decimal, reference: Decimal) -> Decimal:
    if reference <= 0:
        raise ValueError("reference price must be positive")
    return (abs(value - reference) / reference) * Decimal("100")


def _blocked_source_results(
    snapshots: tuple[BenchmarkSnapshot, ...],
    mapping: CrossExchangeSymbolMap,
    reason: str,
) -> tuple[ConsensusSourceResult, ...]:
    return tuple(
        ConsensusSourceResult(
            source=snapshot.source,
            exchange_symbol=snapshot.symbol,
            expected_symbol=mapping.expected_symbol(snapshot.source),
            health_state=None,
            price=snapshot.last_price,
            included=False,
            reasons=(reason,),
        )
        for snapshot in snapshots
    )


def build_cross_exchange_consensus(
    *,
    lbank_snapshot: LBankExecutionSnapshot,
    benchmark_snapshots: tuple[BenchmarkSnapshot, ...],
    symbol_map: CrossExchangeSymbolMap,
    now: datetime,
    rules: ConsensusRules | None = None,
) -> CrossExchangeConsensusReport:
    active_rules = rules or ConsensusRules()
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")

    lbank_price = lbank_snapshot.executable_mid_price
    if not symbol_map.reliable:
        return CrossExchangeConsensusReport(
            canonical_symbol=symbol_map.canonical_symbol,
            lbank_symbol=lbank_snapshot.symbol,
            lbank_price=lbank_price,
            median_benchmark_price=None,
            lbank_deviation_pct=None,
            benchmark_dispersion_pct=None,
            status=ConsensusStatus.DATA_DEGRADED,
            usable_sources=0,
            source_results=_blocked_source_results(
                benchmark_snapshots,
                symbol_map,
                "SYMBOL_MAPPING_UNRELIABLE",
            ),
            reasons=("SYMBOL_MAPPING_UNRELIABLE",),
        )

    if lbank_snapshot.symbol != symbol_map.lbank_symbol:
        return CrossExchangeConsensusReport(
            canonical_symbol=symbol_map.canonical_symbol,
            lbank_symbol=lbank_snapshot.symbol,
            lbank_price=lbank_price,
            median_benchmark_price=None,
            lbank_deviation_pct=None,
            benchmark_dispersion_pct=None,
            status=ConsensusStatus.DATA_DEGRADED,
            usable_sources=0,
            source_results=_blocked_source_results(
                benchmark_snapshots,
                symbol_map,
                "LBANK_SYMBOL_MISMATCH",
            ),
            reasons=("LBANK_SYMBOL_MISMATCH",),
        )

    lbank_validation = validate_lbank_execution(
        lbank_snapshot,
        now=now,
        rules=active_rules.lbank_execution,
    )

    preliminary: list[ConsensusSourceResult] = []
    used_prices: list[Decimal] = []
    seen_sources: set[BenchmarkSource] = set()

    for snapshot in benchmark_snapshots:
        expected_symbol = symbol_map.expected_symbol(snapshot.source)
        reasons: list[str] = []
        health_state: BenchmarkHealthState | None = None
        included = True

        if snapshot.source in seen_sources:
            reasons.append("DUPLICATE_SOURCE")
            included = False
        else:
            seen_sources.add(snapshot.source)

        if expected_symbol is None:
            reasons.append("SOURCE_UNMAPPED")
            included = False
        elif snapshot.symbol != expected_symbol:
            reasons.append("SYMBOL_MISMATCH")
            included = False

        if included:
            health = evaluate_benchmark_health(
                snapshot,
                now=now,
                rules=active_rules.benchmark_health,
            )
            health_state = health.state
            if not health.is_usable:
                reasons.extend(health.reasons)
                included = False

        if included:
            used_prices.append(snapshot.last_price)

        preliminary.append(
            ConsensusSourceResult(
                source=snapshot.source,
                exchange_symbol=snapshot.symbol,
                expected_symbol=expected_symbol,
                health_state=health_state,
                price=snapshot.last_price,
                included=included,
                reasons=tuple(reasons),
            )
        )

    median_price: Decimal | None = None
    lbank_deviation: Decimal | None = None
    dispersion: Decimal | None = None
    source_results = tuple(preliminary)

    if used_prices:
        median_price = median(used_prices)
        lbank_deviation = _deviation_pct(lbank_price, median_price)
        dispersion = ((max(used_prices) - min(used_prices)) / median_price) * Decimal("100")
        source_results = tuple(
            replace(
                result,
                deviation_from_median_pct=(
                    _deviation_pct(result.price, median_price)
                    if result.included
                    else None
                ),
            )
            for result in preliminary
        )

    report_reasons: list[str] = []
    usable_sources = len(used_prices)

    if lbank_validation.status == LBankExecutionStatus.EXECUTION_PENDING:
        report_reasons.extend(lbank_validation.reasons)
        return CrossExchangeConsensusReport(
            canonical_symbol=symbol_map.canonical_symbol,
            lbank_symbol=lbank_snapshot.symbol,
            lbank_price=lbank_price,
            median_benchmark_price=median_price,
            lbank_deviation_pct=lbank_deviation,
            benchmark_dispersion_pct=dispersion,
            status=ConsensusStatus.EXECUTION_PENDING,
            usable_sources=usable_sources,
            source_results=source_results,
            reasons=tuple(report_reasons),
        )

    if lbank_validation.status == LBankExecutionStatus.DATA_DEGRADED:
        report_reasons.extend(lbank_validation.reasons)
        return CrossExchangeConsensusReport(
            canonical_symbol=symbol_map.canonical_symbol,
            lbank_symbol=lbank_snapshot.symbol,
            lbank_price=lbank_price,
            median_benchmark_price=median_price,
            lbank_deviation_pct=lbank_deviation,
            benchmark_dispersion_pct=dispersion,
            status=ConsensusStatus.DATA_DEGRADED,
            usable_sources=usable_sources,
            source_results=source_results,
            reasons=tuple(report_reasons),
        )

    if usable_sources < active_rules.minimum_fresh_sources:
        report_reasons.append("INSUFFICIENT_FRESH_BENCHMARK_SOURCES")
        return CrossExchangeConsensusReport(
            canonical_symbol=symbol_map.canonical_symbol,
            lbank_symbol=lbank_snapshot.symbol,
            lbank_price=lbank_price,
            median_benchmark_price=median_price,
            lbank_deviation_pct=lbank_deviation,
            benchmark_dispersion_pct=dispersion,
            status=ConsensusStatus.DATA_DEGRADED,
            usable_sources=usable_sources,
            source_results=source_results,
            reasons=tuple(report_reasons),
        )

    if dispersion is not None and dispersion > active_rules.max_benchmark_dispersion_pct:
        report_reasons.append("BENCHMARK_DISPERSION_TOO_HIGH")
        return CrossExchangeConsensusReport(
            canonical_symbol=symbol_map.canonical_symbol,
            lbank_symbol=lbank_snapshot.symbol,
            lbank_price=lbank_price,
            median_benchmark_price=median_price,
            lbank_deviation_pct=lbank_deviation,
            benchmark_dispersion_pct=dispersion,
            status=ConsensusStatus.DATA_DEGRADED,
            usable_sources=usable_sources,
            source_results=source_results,
            reasons=tuple(report_reasons),
        )

    if lbank_deviation is None:
        raise ValueError("median price is required after source validation")

    if lbank_deviation >= active_rules.avoid_deviation_pct:
        status = ConsensusStatus.AVOID
        report_reasons.append("LBANK_DEVIATION_AVOID")
    elif lbank_deviation >= active_rules.degraded_deviation_pct:
        status = ConsensusStatus.DATA_DEGRADED
        report_reasons.append("LBANK_DEVIATION_DEGRADED")
    elif lbank_deviation >= active_rules.warning_deviation_pct:
        status = ConsensusStatus.WARNING
        report_reasons.append("LBANK_DEVIATION_WARNING")
    else:
        status = ConsensusStatus.OK

    return CrossExchangeConsensusReport(
        canonical_symbol=symbol_map.canonical_symbol,
        lbank_symbol=lbank_snapshot.symbol,
        lbank_price=lbank_price,
        median_benchmark_price=median_price,
        lbank_deviation_pct=lbank_deviation,
        benchmark_dispersion_pct=dispersion,
        status=status,
        usable_sources=usable_sources,
        source_results=source_results,
        reasons=tuple(report_reasons),
    )
