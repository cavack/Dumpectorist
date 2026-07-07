from datetime import datetime
from decimal import Decimal

from app.execution.consensus import (
    ConsensusStatus,
    build_cross_exchange_consensus,
)
from app.execution.lbank_validator import (
    LBankExecutionStatus,
    validate_lbank_execution,
)
from app.flow.models import FlowStatus
from app.flow.runner import run_flow
from app.lifecycle.service import create_lifecycle
from app.planning.models import PlanDraft, PlanStatus
from app.planning.service import build_plan
from app.setups.classifier import classify_snapshot
from app.structure.analyzer import analyze_structure
from app.structure.models import StructureState
from app.signals.models import (
    GateDecision,
    GateState,
    SignalAssemblyReport,
    SignalAssemblyRequest,
    SignalAssemblyRules,
    SignalAssemblyStatus,
)


GATE_ORDER = (
    "discovery_context",
    "symbol_alignment",
    "higher_timeframe_structure",
    "structure",
    "setup_classification",
    "flow",
    "lbank_execution",
    "cross_exchange_consensus",
    "entry_alignment",
    "planning",
    "lifecycle",
)


def assemble_signal(
    request: SignalAssemblyRequest,
    *,
    now: datetime,
    rules: SignalAssemblyRules | None = None,
) -> SignalAssemblyReport:
    active_rules = rules or SignalAssemblyRules()
    _require_aware(now, "now")
    gates: list[GateDecision] = []

    discovery_gate = _discovery_gate(request, active_rules)
    gates.append(discovery_gate)
    if discovery_gate.state == GateState.FAIL:
        return _finish(
            request,
            now=now,
            rules=active_rules,
            status=SignalAssemblyStatus.DATA_DEGRADED,
            gates=gates,
        )

    symbol_gate = _symbol_gate(request)
    gates.append(symbol_gate)
    if not symbol_gate.passed:
        return _finish(
            request,
            now=now,
            rules=active_rules,
            status=SignalAssemblyStatus.DATA_DEGRADED,
            gates=gates,
        )

    higher_timeframe_gate, higher_timeframe_status = _higher_timeframe_gate(
        request,
        now=now,
        rules=active_rules,
    )
    gates.append(higher_timeframe_gate)
    if not higher_timeframe_gate.passed:
        return _finish(
            request,
            now=now,
            rules=active_rules,
            status=higher_timeframe_status,
            gates=gates,
        )

    try:
        structure = analyze_structure(request.structure_input)
    except Exception as error:
        gates.append(
            GateDecision(
                name="structure",
                state=GateState.FAIL,
                reasons=(_error_reason(error),),
            )
        )
        return _finish(
            request,
            now=now,
            rules=active_rules,
            status=SignalAssemblyStatus.DATA_DEGRADED,
            gates=gates,
        )

    structure_state = (
        GateState.PASS if structure.state == StructureState.ALERT else GateState.FAIL
    )
    gates.append(
        GateDecision(
            name="structure",
            state=structure_state,
            reasons=structure.reasons + (f"STATE_{structure.state.value}",),
        )
    )

    setup = classify_snapshot(structure)
    gates.append(
        GateDecision(
            name="setup_classification",
            state=GateState.PASS if setup.is_actionable else GateState.FAIL,
            reasons=setup.reasons + (f"TYPE_{request.setup_type.value}",),
        )
    )

    flow = run_flow(setup)
    gates.append(
        GateDecision(
            name="flow",
            state=GateState.PASS if flow.status == FlowStatus.READY else GateState.FAIL,
            reasons=flow.reasons + (f"STATUS_{flow.status.value}",),
        )
    )

    if not flow.is_ready:
        return _finish(
            request,
            now=now,
            rules=active_rules,
            status=_watch_status(structure.state),
            gates=gates,
            structure=structure,
            setup=setup,
            flow=flow,
        )

    try:
        lbank_validation = validate_lbank_execution(
            request.lbank_snapshot,
            now=now,
            rules=active_rules.consensus.lbank_execution,
        )
    except Exception as error:
        gates.append(
            GateDecision(
                name="lbank_execution",
                state=GateState.FAIL,
                reasons=(_error_reason(error),),
            )
        )
        return _finish(
            request,
            now=now,
            rules=active_rules,
            status=SignalAssemblyStatus.DATA_DEGRADED,
            gates=gates,
            structure=structure,
            setup=setup,
            flow=flow,
        )

    gates.append(
        GateDecision(
            name="lbank_execution",
            state=(
                GateState.PASS
                if lbank_validation.status == LBankExecutionStatus.OK
                else GateState.FAIL
            ),
            reasons=lbank_validation.reasons
            or (f"STATUS_{lbank_validation.status.value}",),
        )
    )
    if lbank_validation.status != LBankExecutionStatus.OK:
        blocked_status = (
            SignalAssemblyStatus.EXECUTION_PENDING
            if lbank_validation.status == LBankExecutionStatus.EXECUTION_PENDING
            else SignalAssemblyStatus.DATA_DEGRADED
        )
        return _finish(
            request,
            now=now,
            rules=active_rules,
            status=blocked_status,
            gates=gates,
            structure=structure,
            setup=setup,
            flow=flow,
            lbank_validation=lbank_validation,
        )

    try:
        consensus = build_cross_exchange_consensus(
            lbank_snapshot=request.lbank_snapshot,
            benchmark_snapshots=request.benchmark_snapshots,
            symbol_map=request.symbol_map,
            now=now,
            rules=active_rules.consensus,
        )
    except Exception as error:
        gates.append(
            GateDecision(
                name="cross_exchange_consensus",
                state=GateState.FAIL,
                reasons=(_error_reason(error),),
            )
        )
        return _finish(
            request,
            now=now,
            rules=active_rules,
            status=SignalAssemblyStatus.DATA_DEGRADED,
            gates=gates,
            structure=structure,
            setup=setup,
            flow=flow,
            lbank_validation=lbank_validation,
        )

    consensus_gate_state = (
        GateState.PASS
        if consensus.status == ConsensusStatus.OK
        else GateState.WARN
        if consensus.status == ConsensusStatus.WARNING
        else GateState.FAIL
    )
    gates.append(
        GateDecision(
            name="cross_exchange_consensus",
            state=consensus_gate_state,
            reasons=consensus.reasons or (f"STATUS_{consensus.status.value}",),
        )
    )
    if not consensus.allows_execution_confirmation:
        status_map = {
            ConsensusStatus.EXECUTION_PENDING: SignalAssemblyStatus.EXECUTION_PENDING,
            ConsensusStatus.DATA_DEGRADED: SignalAssemblyStatus.DATA_DEGRADED,
            ConsensusStatus.AVOID: SignalAssemblyStatus.AVOID,
        }
        return _finish(
            request,
            now=now,
            rules=active_rules,
            status=status_map.get(
                consensus.status,
                SignalAssemblyStatus.DATA_DEGRADED,
            ),
            gates=gates,
            structure=structure,
            setup=setup,
            flow=flow,
            lbank_validation=lbank_validation,
            consensus=consensus,
        )

    entry_deviation_bps = _entry_deviation_bps(request)
    if entry_deviation_bps > active_rules.max_entry_deviation_bps:
        gates.append(
            GateDecision(
                name="entry_alignment",
                state=GateState.FAIL,
                reasons=(
                    "ENTRY_TOO_FAR_FROM_LBANK",
                    f"DEVIATION_BPS_{entry_deviation_bps}",
                ),
            )
        )
        return _finish(
            request,
            now=now,
            rules=active_rules,
            status=SignalAssemblyStatus.EXECUTION_PENDING,
            gates=gates,
            structure=structure,
            setup=setup,
            flow=flow,
            lbank_validation=lbank_validation,
            consensus=consensus,
            entry_deviation_bps=entry_deviation_bps,
        )

    gates.append(
        GateDecision(
            name="entry_alignment",
            state=GateState.PASS,
            reasons=(f"DEVIATION_BPS_{entry_deviation_bps}",),
        )
    )

    try:
        plan = build_plan(flow, request.plan_request)
    except Exception as error:
        gates.append(
            GateDecision(
                name="planning",
                state=GateState.FAIL,
                reasons=(_error_reason(error),),
            )
        )
        return _finish(
            request,
            now=now,
            rules=active_rules,
            status=SignalAssemblyStatus.DATA_DEGRADED,
            gates=gates,
            structure=structure,
            setup=setup,
            flow=flow,
            lbank_validation=lbank_validation,
            consensus=consensus,
            entry_deviation_bps=entry_deviation_bps,
        )

    if plan.status != PlanStatus.READY:
        gates.append(
            GateDecision(
                name="planning",
                state=GateState.FAIL,
                reasons=plan.notes or ("PLAN_NOT_READY",),
            )
        )
        return _finish(
            request,
            now=now,
            rules=active_rules,
            status=SignalAssemblyStatus.DATA_DEGRADED,
            gates=gates,
            structure=structure,
            setup=setup,
            flow=flow,
            lbank_validation=lbank_validation,
            consensus=consensus,
            entry_deviation_bps=entry_deviation_bps,
            plan=plan,
        )

    gates.append(
        GateDecision(
            name="planning",
            state=GateState.PASS,
            reasons=plan.notes or ("PLAN_READY",),
        )
    )
    lifecycle = create_lifecycle(
        plan,
        now,
        ttl_minutes=active_rules.lifecycle_ttl_minutes,
    )
    gates.append(
        GateDecision(
            name="lifecycle",
            state=GateState.PASS,
            reasons=(f"STATE_{lifecycle.state.value}",),
        )
    )

    return _finish(
        request,
        now=now,
        rules=active_rules,
        status=SignalAssemblyStatus.SHORT_READY,
        gates=gates,
        structure=structure,
        setup=setup,
        flow=flow,
        lbank_validation=lbank_validation,
        consensus=consensus,
        entry_deviation_bps=entry_deviation_bps,
        plan=plan,
        lifecycle=lifecycle,
    )


def _discovery_gate(
    request: SignalAssemblyRequest,
    rules: SignalAssemblyRules,
) -> GateDecision:
    count = len(request.discovery_records)
    if count > rules.max_discovery_records:
        return GateDecision(
            name="discovery_context",
            state=GateState.FAIL,
            reasons=("DISCOVERY_CONTEXT_TOO_LARGE", f"COUNT_{count}"),
        )
    if count == 0:
        return GateDecision(
            name="discovery_context",
            state=GateState.WARN,
            reasons=("DISCOVERY_CONTEXT_EMPTY",),
        )
    sources = sorted({record.source.value for record in request.discovery_records})
    return GateDecision(
        name="discovery_context",
        state=GateState.PASS,
        reasons=(f"COUNT_{count}",) + tuple(f"SOURCE_{source}" for source in sources),
    )


def _symbol_gate(request: SignalAssemblyRequest) -> GateDecision:
    expected = request.symbol
    checks = {
        "CANONICAL": request.symbol_map.canonical_symbol,
        "HIGHER_TIMEFRAME": request.higher_timeframe.symbol,
        "STRUCTURE": request.structure_input.symbol,
        "PLAN": request.plan_request.symbol.strip(),
    }
    reasons = tuple(
        f"{name}_SYMBOL_MISMATCH"
        for name, value in checks.items()
        if value != expected
    )
    if request.lbank_snapshot.symbol != request.symbol_map.lbank_symbol:
        reasons += ("LBANK_SYMBOL_MISMATCH",)
    return GateDecision(
        name="symbol_alignment",
        state=GateState.FAIL if reasons else GateState.PASS,
        reasons=reasons or ("SYMBOLS_ALIGNED",),
    )


def _higher_timeframe_gate(
    request: SignalAssemblyRequest,
    *,
    now: datetime,
    rules: SignalAssemblyRules,
) -> tuple[GateDecision, SignalAssemblyStatus]:
    age_minutes = (now - request.higher_timeframe.observed_at).total_seconds() / 60
    degraded: list[str] = []
    missing_damage: list[str] = []
    if age_minutes < -(1 / 60):
        degraded.append("STRUCTURE_EVIDENCE_FROM_FUTURE")
    elif age_minutes > rules.max_structure_age_minutes:
        degraded.append("STRUCTURE_EVIDENCE_STALE")
    if not request.higher_timeframe.daily_damaged:
        missing_damage.append("DAILY_STRUCTURE_NOT_DAMAGED")
    if not request.higher_timeframe.four_hour_damaged:
        missing_damage.append("FOUR_HOUR_STRUCTURE_NOT_DAMAGED")

    reasons = tuple(degraded + missing_damage) + request.higher_timeframe.reasons
    if degraded:
        return (
            GateDecision(
                name="higher_timeframe_structure",
                state=GateState.FAIL,
                reasons=reasons,
            ),
            SignalAssemblyStatus.DATA_DEGRADED,
        )
    if missing_damage:
        return (
            GateDecision(
                name="higher_timeframe_structure",
                state=GateState.FAIL,
                reasons=reasons,
            ),
            SignalAssemblyStatus.BREAKDOWN_WATCH,
        )
    return (
        GateDecision(
            name="higher_timeframe_structure",
            state=GateState.PASS,
            reasons=(f"AGE_MINUTES_{age_minutes:.2f}",) + request.higher_timeframe.reasons,
        ),
        SignalAssemblyStatus.SHORT_READY,
    )


def _entry_deviation_bps(request: SignalAssemblyRequest) -> Decimal:
    entry = Decimal(str(request.plan_request.entry_value))
    reference = request.lbank_snapshot.executable_mid_price
    if entry <= 0 or reference <= 0:
        raise ValueError("entry and LBank reference must be positive")
    return (abs(entry - reference) / reference) * Decimal("10000")


def _watch_status(state: StructureState) -> SignalAssemblyStatus:
    if state == StructureState.NEUTRAL:
        return SignalAssemblyStatus.HYPE_WATCH
    if state == StructureState.WEAK:
        return SignalAssemblyStatus.WEAKNESS_WATCH
    return SignalAssemblyStatus.BREAKDOWN_WATCH


def _finish(
    request: SignalAssemblyRequest,
    *,
    now: datetime,
    rules: SignalAssemblyRules,
    status: SignalAssemblyStatus,
    gates: list[GateDecision],
    structure=None,
    setup=None,
    flow=None,
    lbank_validation=None,
    consensus=None,
    entry_deviation_bps: Decimal | None = None,
    plan: PlanDraft | None = None,
    lifecycle=None,
) -> SignalAssemblyReport:
    completed_gates = _complete_gates(gates)
    reasons = tuple(
        f"{gate.name}:{reason}"
        for gate in completed_gates
        for reason in gate.reasons
    )
    active_plan = plan or PlanDraft(
        symbol=request.symbol,
        status=PlanStatus.HOLD,
        notes=reasons or ("ASSEMBLY_HELD",),
    )
    active_lifecycle = lifecycle or create_lifecycle(
        active_plan,
        now,
        ttl_minutes=rules.lifecycle_ttl_minutes,
    )
    return SignalAssemblyReport(
        symbol=request.symbol,
        setup_type=request.setup_type,
        status=status,
        assembled_at=now,
        discovery_records=request.discovery_records,
        higher_timeframe=request.higher_timeframe,
        gates=completed_gates,
        reasons=reasons,
        plan=active_plan,
        lifecycle=active_lifecycle,
        structure=structure,
        setup=setup,
        flow=flow,
        lbank_validation=lbank_validation,
        consensus=consensus,
        entry_deviation_bps=entry_deviation_bps,
    )


def _complete_gates(gates: list[GateDecision]) -> tuple[GateDecision, ...]:
    by_name = {gate.name: gate for gate in gates}
    return tuple(
        by_name.get(
            name,
            GateDecision(
                name=name,
                state=GateState.SKIP,
                reasons=("NOT_EVALUATED",),
            ),
        )
        for name in GATE_ORDER
    )


def _require_aware(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")


def _error_reason(error: Exception) -> str:
    detail = str(error).strip()
    return f"{type(error).__name__}:{detail}"[:500] if detail else type(error).__name__
