from app.flow.models import FlowResult
from app.planning.models import PlanDraft, PlanRequest, PlanStatus


def build_plan(flow: FlowResult, request: PlanRequest) -> PlanDraft:
    if not flow.is_ready:
        return PlanDraft(
            symbol=request.symbol,
            status=PlanStatus.HOLD,
            notes=("flow is not ready",),
        )

    symbol = request.symbol.strip()
    if not symbol:
        raise ValueError("symbol is required")
    if request.entry_value <= 0 or request.boundary_value <= 0:
        raise ValueError("plan values must be positive")
    if request.boundary_value <= request.entry_value:
        raise ValueError("boundary must be above entry")
    if request.ratio <= 0:
        raise ValueError("ratio must be positive")
    if request.multiplier < 1 or request.multiplier > 5:
        raise ValueError("multiplier must be between 1 and 5")

    distance = request.boundary_value - request.entry_value
    objective_value = request.entry_value - (distance * request.ratio)
    if objective_value <= 0:
        raise ValueError("objective must remain positive")

    return PlanDraft(
        symbol=symbol,
        status=PlanStatus.READY,
        entry_value=request.entry_value,
        boundary_value=request.boundary_value,
        objective_value=objective_value,
        multiplier=request.multiplier,
        ratio=request.ratio,
        notes=("plan created",),
    )
