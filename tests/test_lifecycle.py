from datetime import datetime, timedelta, timezone

import pytest

from app.lifecycle.models import LifecycleState
from app.lifecycle.service import advance_lifecycle, create_lifecycle
from app.strategy.review import PlanDraft, PlanStatus


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


def test_record_expires_at_due_time():
    plan = PlanDraft(symbol="TEST", status=PlanStatus.READY)
    record = create_lifecycle(plan, NOW, ttl_minutes=30)

    result = advance_lifecycle(record, NOW + timedelta(minutes=30))

    assert result.state == LifecycleState.EXPIRED
    assert result.is_terminal is True


def test_non_positive_ttl_is_rejected():
    plan = PlanDraft(symbol="TEST", status=PlanStatus.READY)

    with pytest.raises(ValueError):
        create_lifecycle(plan, NOW, ttl_minutes=0)


def test_naive_timestamp_is_rejected():
    plan = PlanDraft(symbol="TEST", status=PlanStatus.READY)

    with pytest.raises(ValueError):
        create_lifecycle(plan, datetime(2026, 7, 7, 12, 0))
