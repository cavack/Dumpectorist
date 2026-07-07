import pytest

from app.flow.models import FlowResult, FlowStatus
from app.planning import PlanRequest, PlanStatus, build_plan


def ready_flow() -> FlowResult:
    return FlowResult(symbol="TEST", status=FlowStatus.READY)


def test_plan_holds_when_flow_is_not_ready():
    flow = FlowResult(symbol="TEST", status=FlowStatus.WAIT)
    request = PlanRequest(symbol="TEST", entry_value=10.0, boundary_value=11.0)

    plan = build_plan(flow, request)

    assert plan.status == PlanStatus.HOLD
    assert plan.entry_value is None


def test_ready_flow_builds_plan():
    request = PlanRequest(
        symbol="TEST",
        entry_value=10.0,
        boundary_value=11.0,
        multiplier=3,
        ratio=2.0,
    )

    plan = build_plan(ready_flow(), request)

    assert plan.status == PlanStatus.READY
    assert plan.objective_value == 8.0
    assert plan.multiplier == 3


def test_multiplier_above_five_is_rejected():
    request = PlanRequest(
        symbol="TEST",
        entry_value=10.0,
        boundary_value=11.0,
        multiplier=6,
    )

    with pytest.raises(ValueError):
        build_plan(ready_flow(), request)


def test_multiplier_below_one_is_rejected():
    request = PlanRequest(
        symbol="TEST",
        entry_value=10.0,
        boundary_value=11.0,
        multiplier=0,
    )

    with pytest.raises(ValueError):
        build_plan(ready_flow(), request)


def test_boundary_must_be_above_entry():
    request = PlanRequest(symbol="TEST", entry_value=10.0, boundary_value=9.0)

    with pytest.raises(ValueError):
        build_plan(ready_flow(), request)


def test_non_positive_ratio_is_rejected():
    request = PlanRequest(
        symbol="TEST",
        entry_value=10.0,
        boundary_value=11.0,
        ratio=0,
    )

    with pytest.raises(ValueError):
        build_plan(ready_flow(), request)


def test_non_positive_objective_is_rejected():
    request = PlanRequest(
        symbol="TEST",
        entry_value=10.0,
        boundary_value=20.0,
        ratio=1.0,
    )

    with pytest.raises(ValueError):
        build_plan(ready_flow(), request)
