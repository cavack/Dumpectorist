import pytest

from app.notifications.delivery import DisabledDelivery
from app.notifications.formatter import format_plan_message
from app.notifications.models import DeliveryStatus, NotificationChannel
from app.planning.models import PlanDraft, PlanStatus


def test_ready_plan_formats_all_required_values():
    plan = PlanDraft(
        symbol="TEST",
        status=PlanStatus.READY,
        entry_value=10.0,
        boundary_value=11.0,
        objective_value=8.0,
        multiplier=3,
        ratio=2.0,
    )

    message = format_plan_message(plan)

    assert message.channel == NotificationChannel.TELEGRAM
    assert message.title == "TEST plan update"
    assert "Status: READY" in message.body
    assert "Entry: 10" in message.body
    assert "Boundary: 11" in message.body
    assert "Objective: 8" in message.body
    assert message.metadata["multiplier"] == "3"


def test_hold_plan_formats_without_numeric_values():
    plan = PlanDraft(
        symbol="TEST",
        status=PlanStatus.HOLD,
        notes=("flow is not ready",),
    )

    message = format_plan_message(plan, NotificationChannel.DASHBOARD)

    assert message.channel == NotificationChannel.DASHBOARD
    assert "Status: HOLD" in message.body
    assert "flow is not ready" in message.body


def test_incomplete_ready_plan_is_rejected():
    plan = PlanDraft(symbol="TEST", status=PlanStatus.READY)

    with pytest.raises(ValueError):
        format_plan_message(plan)


@pytest.mark.asyncio
async def test_disabled_delivery_skips_external_send():
    plan = PlanDraft(
        symbol="TEST",
        status=PlanStatus.HOLD,
        notes=("waiting",),
    )
    message = format_plan_message(plan)

    receipt = await DisabledDelivery().deliver(message)

    assert receipt.status == DeliveryStatus.SKIPPED
    assert receipt.symbol == "TEST"
    assert receipt.detail == "delivery disabled"
