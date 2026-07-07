from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.benchmark_models import BenchmarkSnapshot
from app.adapters.lbank_models import LBankExecutionSnapshot
from app.db.repository import DomainRecordInput, DomainRecordRepository
from app.execution.consensus import (
    ConsensusRules,
    ConsensusStatus,
    CrossExchangeConsensusReport,
    build_cross_exchange_consensus,
)
from app.execution.liquidity_models import ExecutionReadiness, OrderRecommendation
from app.execution.order_constraints import ExecutionOrderRequest
from app.execution.reality import ExecutionRealityReport, evaluate_execution_reality
from app.execution.symbol_mapping import CrossExchangeSymbolMap
from app.runtime.store import json_safe


@dataclass(frozen=True)
class SourceClockAudit:
    source: str
    delta_seconds: float
    included: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class ReadinessAudit:
    symbol: str
    evaluated_at: datetime
    readiness: ExecutionReadiness
    recommendation: OrderRecommendation
    reality: ExecutionRealityReport
    consensus: CrossExchangeConsensusReport
    source_clocks: tuple[SourceClockAudit, ...]
    reasons: tuple[str, ...]
    warnings: tuple[str, ...]

    def __post_init__(self):
        if not self.symbol.strip():
            raise ValueError("symbol is required")
        if self.evaluated_at.tzinfo is None or self.evaluated_at.utcoffset() is None:
            raise ValueError("evaluated_at must be timezone-aware")

    @property
    def executable(self):
        return self.readiness == ExecutionReadiness.EXECUTABLE

    @property
    def audit_id(self):
        raw = "|".join(
            (
                self.symbol,
                self.evaluated_at.isoformat(),
                self.readiness.value,
                self.consensus.status.value,
                str(self.consensus.usable_sources),
            )
        )
        return f"exec_{sha256(raw.encode('utf-8')).hexdigest()[:24]}"


def evaluate_readiness(
    *,
    lbank_snapshot: LBankExecutionSnapshot,
    benchmark_snapshots: tuple[BenchmarkSnapshot, ...],
    symbol_map: CrossExchangeSymbolMap,
    now: datetime,
    contract_active: bool | None,
    order_request: ExecutionOrderRequest | None = None,
    max_source_clock_delta_seconds: float = 10.0,
    consensus_rules: ConsensusRules | None = None,
) -> ReadinessAudit:
    if max_source_clock_delta_seconds <= 0:
        raise ValueError("max_source_clock_delta_seconds must be positive")

    aligned: list[BenchmarkSnapshot] = []
    clock_audit: list[SourceClockAudit] = []
    for snapshot in benchmark_snapshots:
        source_time = snapshot.source_timestamp or snapshot.received_at
        delta = abs((source_time - lbank_snapshot.received_at).total_seconds())
        included = delta <= max_source_clock_delta_seconds
        reasons = () if included else ("SOURCE_TIMESTAMP_DELTA_TOO_HIGH",)
        clock_audit.append(
            SourceClockAudit(
                source=snapshot.source.value,
                delta_seconds=delta,
                included=included,
                reasons=reasons,
            )
        )
        if included:
            aligned.append(snapshot)

    reality = evaluate_execution_reality(
        lbank_snapshot,
        now=now,
        contract_active=contract_active,
        order_request=order_request,
    )
    consensus = build_cross_exchange_consensus(
        lbank_snapshot=lbank_snapshot,
        benchmark_snapshots=tuple(aligned),
        symbol_map=symbol_map,
        now=now,
        rules=consensus_rules,
    )

    reasons = list(reality.reasons)
    warnings = list(reality.warnings)
    excluded = [item for item in clock_audit if not item.included]
    if excluded:
        warnings.append("BENCHMARK_TIMESTAMP_ALIGNMENT_EXCLUSIONS")

    if reality.readiness == ExecutionReadiness.DATA_DEGRADED:
        readiness = ExecutionReadiness.DATA_DEGRADED
        recommendation = OrderRecommendation.NO_ORDER
    elif reality.readiness == ExecutionReadiness.NO_TRADE:
        readiness = ExecutionReadiness.NO_TRADE
        recommendation = OrderRecommendation.NO_ORDER
    elif consensus.status == ConsensusStatus.AVOID:
        readiness = ExecutionReadiness.NO_TRADE
        recommendation = OrderRecommendation.NO_ORDER
        reasons.extend(consensus.reasons)
    elif consensus.status == ConsensusStatus.DATA_DEGRADED:
        readiness = ExecutionReadiness.DATA_DEGRADED
        recommendation = OrderRecommendation.NO_ORDER
        reasons.extend(consensus.reasons)
    elif (
        reality.readiness == ExecutionReadiness.EXECUTION_PENDING
        or consensus.status == ConsensusStatus.EXECUTION_PENDING
    ):
        readiness = ExecutionReadiness.EXECUTION_PENDING
        recommendation = reality.recommendation
        reasons.extend(consensus.reasons)
    else:
        readiness = ExecutionReadiness.EXECUTABLE
        recommendation = reality.recommendation
        if consensus.status == ConsensusStatus.WARNING:
            warnings.extend(consensus.reasons)

    return ReadinessAudit(
        symbol=lbank_snapshot.symbol,
        evaluated_at=now,
        readiness=readiness,
        recommendation=recommendation,
        reality=reality,
        consensus=consensus,
        source_clocks=tuple(clock_audit),
        reasons=tuple(dict.fromkeys(reasons)),
        warnings=tuple(dict.fromkeys(warnings)),
    )


async def persist_readiness_audit(
    session: AsyncSession,
    audit: ReadinessAudit,
):
    repository = DomainRecordRepository(session)
    return await repository.add(
        DomainRecordInput(
            record_type="execution_gate_audit",
            symbol=audit.symbol,
            state=audit.readiness.value,
            payload=json_safe(
                {
                    "audit_id": audit.audit_id,
                    "evaluated_at": audit.evaluated_at,
                    "recommendation": audit.recommendation,
                    "reality": audit.reality,
                    "consensus": audit.consensus,
                    "source_clocks": audit.source_clocks,
                    "reasons": audit.reasons,
                    "warnings": audit.warnings,
                }
            ),
        )
    )
