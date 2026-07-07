from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from app.adapters.lbank_models import LBankExecutionSnapshot
from app.execution.lbank_validator import (
    LBankExecutionRules,
    LBankExecutionStatus,
    LBankExecutionValidation,
    validate_lbank_execution,
)
from app.execution.liquidity import assess_lbank_liquidity
from app.execution.liquidity_models import (
    ExecutionReadiness,
    LiquidityAssessment,
    LiquidityRules,
    OrderRecommendation,
)
from app.execution.order_constraints import (
    ExecutionOrderRequest,
    OrderConstraintValidation,
    validate_order_constraints,
)


class ExecutionGateState(StrEnum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ExecutionGateDecision:
    name: str
    state: ExecutionGateState
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self):
        if not self.name.strip():
            raise ValueError("gate name is required")


@dataclass(frozen=True)
class ExecutionRealityReport:
    symbol: str
    evaluated_at: datetime
    readiness: ExecutionReadiness
    recommendation: OrderRecommendation
    lbank: LBankExecutionValidation
    liquidity: LiquidityAssessment
    order_constraints: OrderConstraintValidation | None
    gates: tuple[ExecutionGateDecision, ...]
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


def evaluate_execution_reality(
    snapshot: LBankExecutionSnapshot,
    *,
    now: datetime,
    contract_active: bool | None,
    order_request: ExecutionOrderRequest | None = None,
    lbank_rules: LBankExecutionRules | None = None,
    liquidity_rules: LiquidityRules | None = None,
) -> ExecutionRealityReport:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")

    lbank = validate_lbank_execution(snapshot, now=now, rules=lbank_rules)
    liquidity = assess_lbank_liquidity(snapshot, rules=liquidity_rules)
    constraints = (
        None
        if order_request is None
        else validate_order_constraints(order_request, snapshot.instrument)
    )

    gates: list[ExecutionGateDecision] = []
    reasons: list[str] = []
    warnings: list[str] = list(liquidity.warnings)

    if contract_active is None:
        gates.append(
            ExecutionGateDecision(
                name="contract_active",
                state=ExecutionGateState.UNKNOWN,
                reasons=("CONTRACT_STATUS_UNAVAILABLE",),
            )
        )
        reasons.append("CONTRACT_STATUS_UNAVAILABLE")
    elif contract_active is False:
        gates.append(
            ExecutionGateDecision(
                name="contract_active",
                state=ExecutionGateState.FAIL,
                reasons=("CONTRACT_INACTIVE",),
            )
        )
        reasons.append("CONTRACT_INACTIVE")
    else:
        gates.append(
            ExecutionGateDecision(
                name="contract_active",
                state=ExecutionGateState.PASS,
            )
        )

    lbank_state = (
        ExecutionGateState.PASS
        if lbank.status == LBankExecutionStatus.OK
        else ExecutionGateState.FAIL
    )
    gates.append(
        ExecutionGateDecision(
            name="lbank_snapshot",
            state=lbank_state,
            reasons=lbank.reasons,
        )
    )
    reasons.extend(lbank.reasons)

    liquidity_state = {
        ExecutionReadiness.EXECUTABLE: ExecutionGateState.PASS,
        ExecutionReadiness.EXECUTION_PENDING: ExecutionGateState.WARN,
        ExecutionReadiness.DATA_DEGRADED: ExecutionGateState.UNKNOWN,
        ExecutionReadiness.NO_TRADE: ExecutionGateState.FAIL,
    }[liquidity.readiness]
    gates.append(
        ExecutionGateDecision(
            name="liquidity",
            state=liquidity_state,
            reasons=liquidity.reasons + liquidity.warnings,
        )
    )
    reasons.extend(liquidity.reasons)

    constraint_missing = False
    constraint_failed = False
    if constraints is not None:
        constraint_missing = any(reason.endswith("UNAVAILABLE") for reason in constraints.reasons)
        constraint_failed = not constraints.valid and not constraint_missing
        gates.append(
            ExecutionGateDecision(
                name="order_constraints",
                state=(
                    ExecutionGateState.PASS
                    if constraints.valid
                    else (
                        ExecutionGateState.UNKNOWN
                        if constraint_missing
                        else ExecutionGateState.FAIL
                    )
                ),
                reasons=constraints.reasons,
            )
        )
        reasons.extend(constraints.reasons)

    if contract_active is None or lbank.status == LBankExecutionStatus.DATA_DEGRADED:
        readiness = ExecutionReadiness.DATA_DEGRADED
        recommendation = OrderRecommendation.NO_ORDER
    elif contract_active is False:
        readiness = ExecutionReadiness.NO_TRADE
        recommendation = OrderRecommendation.NO_ORDER
    elif constraint_missing:
        readiness = ExecutionReadiness.DATA_DEGRADED
        recommendation = OrderRecommendation.NO_ORDER
    elif constraint_failed or liquidity.readiness == ExecutionReadiness.NO_TRADE:
        readiness = ExecutionReadiness.NO_TRADE
        recommendation = OrderRecommendation.NO_ORDER
    elif (
        lbank.status == LBankExecutionStatus.EXECUTION_PENDING
        or liquidity.readiness == ExecutionReadiness.EXECUTION_PENDING
    ):
        readiness = ExecutionReadiness.EXECUTION_PENDING
        recommendation = liquidity.recommendation
    else:
        readiness = ExecutionReadiness.EXECUTABLE
        recommendation = liquidity.recommendation

    return ExecutionRealityReport(
        symbol=snapshot.symbol,
        evaluated_at=now,
        readiness=readiness,
        recommendation=recommendation,
        lbank=lbank,
        liquidity=liquidity,
        order_constraints=constraints,
        gates=tuple(gates),
        reasons=tuple(dict.fromkeys(reasons)),
        warnings=tuple(dict.fromkeys(warnings)),
    )
