from dataclasses import dataclass, field
from enum import StrEnum

from app.flow.models import FlowResult


@dataclass(frozen=True)
class CandidateReview:
    symbol: str
    structure_ok: bool = False
    validation_ok: bool = False
    freshness_ok: bool = False
    notes: tuple[str, ...] = field(default_factory=tuple)


class PlanStatus(StrEnum):
    HOLD = "HOLD"
    READY = "READY"


@dataclass(frozen=True)
class PlanDraft:
    symbol: str
    status: PlanStatus
    entry_value: float | None = None
    boundary_value: float | None = None
    objective_value: float | None = None
    multiplier: int = 1
    ratio: float = 2.0
    notes: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class PlanRequest:
    symbol: str
    entry_value: float
    boundary_value: float
    multiplier: int = 1
    ratio: float = 2.0


def classify_candidate(review: CandidateReview) -> str:
    if review.structure_ok and review.validation_ok and review.freshness_ok:
        return "READY"
    if review.structure_ok:
        return "REVIEW"
    return "WATCH"


def build_plan(flow: FlowResult, request: PlanRequest) -> PlanDraft:
    if not flow.is_ready:
        return PlanDraft(
            symbol=request.symbol,
            status=PlanStatus.HOLD,
            notes=("flow is not ready",),
        )

    if request.entry_value <= 0 or request.boundary_value <= 0:
        raise ValueError("plan values must be positive")
    if request.entry_value == request.boundary_value:
        raise ValueError("plan values must differ")
    if request.ratio <= 0:
        raise ValueError("ratio must be positive")

    multiplier = min(max(request.multiplier, 1), 5)
    distance = abs(request.boundary_value - request.entry_value)
    objective_value = request.entry_value - (distance * request.ratio)

    return PlanDraft(
        symbol=request.symbol,
        status=PlanStatus.READY,
        entry_value=request.entry_value,
        boundary_value=request.boundary_value,
        objective_value=objective_value,
        multiplier=multiplier,
        ratio=request.ratio,
        notes=("plan created",),
    )
