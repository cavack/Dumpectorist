import pytest

from app.flow.models import FlowResult, FlowStatus
from app.strategy.review import (
    CandidateReview,
    PlanRequest,
    PlanStatus,
    build_plan,
    classify_candidate,
)


def test_candidate_starts_in_watch_when_structure_is_missing():
    review = CandidateReview(symbol="TEST")

    assert classify_candidate(review) == "WATCH"


def test_candidate_moves_to_review_after_structure_check():
    review = CandidateReview(symbol="TEST", structure_ok=True)

    assert classify_candidate(review) == "REVIEW"


def test_candidate_moves_to_ready_after_all_checks():
    review = CandidateReview(
        symbol="TEST",
        structure_ok=True,
        validation_ok=True,
        freshness_ok=True,
    )

    assert classify_candidate(review) == "READY"


def test_plan_holds_when_flow_is_not_ready():
    flow = FlowResult(symbol="TEST", status=FlowStatus.WAIT)
    request = PlanRequest(symbol="TEST", entry_value=10.0, boundary_value=11.0)

    plan = build_plan(flow, request)

    assert plan.status == PlanStatus.HOLD
    assert plan.entry_value is None


def test_ready_flow_builds_plan():
    flow = FlowResult(symbol="TEST", status=FlowStatus.READY)
    request = PlanRequest(
        symbol="TEST",
        entry_value=10.0,
        boundary_value=11.0,
        multiplier=3,
        ratio=2.0,
    )

    plan = build_plan(flow, request)

    assert plan.status == PlanStatus.READY
    assert plan.objective_value == 8.0
    assert plan.multiplier == 3


def test_plan_caps_multiplier_at_five():
    flow = FlowResult(symbol="TEST", status=FlowStatus.READY)
    request = PlanRequest(
        symbol="TEST",
        entry_value=10.0,
        boundary_value=11.0,
        multiplier=9,
    )

    plan = build_plan(flow, request)

    assert plan.multiplier == 5


def test_plan_rejects_equal_values():
    flow = FlowResult(symbol="TEST", status=FlowStatus.READY)
    request = PlanRequest(symbol="TEST", entry_value=10.0, boundary_value=10.0)

    with pytest.raises(ValueError):
        build_plan(flow, request)


def test_plan_rejects_non_positive_ratio():
    flow = FlowResult(symbol="TEST", status=FlowStatus.READY)
    request = PlanRequest(
        symbol="TEST",
        entry_value=10.0,
        boundary_value=11.0,
        ratio=0,
    )

    with pytest.raises(ValueError):
        build_plan(flow, request)
