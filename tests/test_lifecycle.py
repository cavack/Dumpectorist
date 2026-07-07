from datetime import datetime, timedelta, timezone

import pytest

from app.lifecycle.models import LifecycleState
from app.lifecycle.service import (
    activate_lifecycle,
    advance_lifecycle,
    close_lifecycle,
    create_lifecycle,
)
from app.planning.models import PlanDraft, PlanStatus


NOW = datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)


def test_ready_plan_starts_active():
    plan = PlanDraft(symbol="TEST", status=PlanStatus.READY)
    record = create_lifecycle(plan, NOW, ttl_minutes=30)

    assert record.state == LifecycleState.ACTIVE
    assert record.expires_at == NOW + timedelta(minutes=30)


def test_held_plan_starts_pending():
    plan = PlanDraft(symbol="TEST", status=PlanStatus.HOLD)
    record = create_lifecycle(plan, NOW)

    assert record.state == LifecycleState.PENDING


def test_pending_record_can_activate():
    plan = PlanDraft(symbol="TEST", status=PlanStatus.HOLD)
    record = create_lifecycle(plan, NOW, ttl_minutes=30)

    result = activate_lifecycle(record, NOW + timedelta(minutes=5))

    assert result.state == LifecycleState.ACTIVE


def test_record_expires_at_due_time():
    plan = PlanDraft(symbol="TEST", status=PlanStatus.READY)
    record = create_lifecycle(plan, NOW, ttl_minutes=30)

    result = advance_lifecycle(record, NOW + timedelta(minutes=30))

    assert result.state == LifecycleState.EXPIRED
    assert result.is_terminal is True


def test_manual_close_marks_record_terminal():
    plan = PlanDraft(symbol="TEST", status=PlanStatus.READY)
    record = create_lifecycle(plan, NOW)
    closed_at = NOW + timedelta(minutes=10)

    result = close_lifecycle(record, closed_at, "manual close")

    assert result.state == LifecycleState.CLOSED
    assert result.closed_at == closed_at
    assert result.is_terminal is True


def test_terminal_record_does_not_transition_again():
    plan = PlanDraft(symbol="TEST", status=PlanStatus.READY)
    record = create_lifecycle(plan, NOW, ttl_minutes=5)
    expired = advance_lifecycle(record, NOW + timedelta(minutes=5))

    result = close_lifecycle(expired, NOW + timedelta(minutes=6))

    assert result == expired


def test_non_positive_ttl_is_rejected():
    plan = PlanDraft(symbol="TEST", status=PlanStatus.READY)

    with pytest.raises(ValueError):
        create_lifecycle(plan, NOW, ttl_minutes=0)


def test_naive_timestamp_is_rejected():
    plan = PlanDraft(symbol="TEST", status=PlanStatus.READY)

    with pytest.raises(ValueError):
        create_lifecycle(plan, datetime(2026, 7, 7, 12, 0))


def test_time_cannot_move_backwards():
    plan = PlanDraft(symbol="TEST", status=PlanStatus.READY)
    record = create_lifecycle(plan, NOW)

    with pytest.raises(ValueError):
        advance_lifecycle(record, NOW - timedelta(seconds=1))
