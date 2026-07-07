from dataclasses import replace

from app.execution.liquidity_models import ExecutionReadiness
from app.execution.readiness import ReadinessAudit
from app.signals.models import GateDecision, GateState, SignalAssemblyStatus
from app.signals.service import assemble_signal


_STATUS_MAP = {
    ExecutionReadiness.EXECUTION_PENDING: SignalAssemblyStatus.EXECUTION_PENDING,
    ExecutionReadiness.DATA_DEGRADED: SignalAssemblyStatus.DATA_DEGRADED,
    ExecutionReadiness.NO_TRADE: SignalAssemblyStatus.AVOID,
}


def assemble_with_readiness(request, *, readiness: ReadinessAudit, now, rules=None):
    if readiness.symbol != request.lbank_snapshot.symbol:
        raise ValueError("readiness symbol does not match LBank snapshot")

    report = assemble_signal(request, now=now, rules=rules)
    if report.status != SignalAssemblyStatus.SHORT_READY:
        return report
    if readiness.readiness == ExecutionReadiness.EXECUTABLE:
        return report

    mapped_status = _STATUS_MAP[readiness.readiness]
    gates = tuple(
        GateDecision(
            name=gate.name,
            state=GateState.FAIL,
            reasons=readiness.reasons
            or (f"READINESS_{readiness.readiness.value}",),
        )
        if gate.name == "lbank_execution"
        else gate
        for gate in report.gates
    )
    reasons = tuple(
        f"execution_readiness:{reason}"
        for reason in readiness.reasons
        or (f"READINESS_{readiness.readiness.value}",)
    )
    return replace(
        report,
        status=mapped_status,
        gates=gates,
        reasons=report.reasons + reasons,
    )
