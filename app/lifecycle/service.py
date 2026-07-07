from dataclasses import replace
from datetime import datetime, timedelta

from app.lifecycle.models import LifecycleRecord, LifecycleState
from app.planning.models import PlanDraft, PlanStatus


def _require_aware(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")


def _require_forward_time(record: LifecycleRecord, now: datetime) -> None:
    _require_aware(now, "now")
    if now < record.updated_at:
        raise ValueError("time cannot move backwards")


def create_lifecycle(
    plan: PlanDraft,
    now: datetime,
    ttl_minutes: int = 60,
) -> LifecycleRecord:
    _require_aware(now, "now")
    if ttl_minutes <= 0:
        raise ValueError("ttl_minutes must be positive")

    state = LifecycleState.ACTIVE if plan.status == PlanStatus.READY else LifecycleState.PENDING
    note = "ready plan activated" if state == LifecycleState.ACTIVE else "held plan pending"

    return LifecycleRecord(
        symbol=plan.symbol,
        state=state,
        created_at=now,
        updated_at=now,
        expires_at=now + timedelta(minutes=ttl_minutes),
        notes=(note,),
    )


def advance_lifecycle(record: LifecycleRecord, now: datetime) -> LifecycleRecord:
    _require_forward_time(record, now)
    if record.is_terminal:
        return record
    if now < record.expires_at:
        return record

    return replace(
        record,
        state=LifecycleState.EXPIRED,
        updated_at=now,
        notes=record.notes + ("expired",),
    )


def activate_lifecycle(record: LifecycleRecord, now: datetime) -> LifecycleRecord:
    _require_forward_time(record, now)
    if record.is_terminal or record.state == LifecycleState.ACTIVE:
        return record
    if now >= record.expires_at:
        return advance_lifecycle(record, now)

    return replace(
        record,
        state=LifecycleState.ACTIVE,
        updated_at=now,
        notes=record.notes + ("activated",),
    )


def close_lifecycle(
    record: LifecycleRecord,
    now: datetime,
    note: str = "closed",
) -> LifecycleRecord:
    _require_forward_time(record, now)
    if record.is_terminal:
        return record

    normalized_note = note.strip() or "closed"
    return replace(
        record,
        state=LifecycleState.CLOSED,
        updated_at=now,
        closed_at=now,
        notes=record.notes + (normalized_note,),
    )
