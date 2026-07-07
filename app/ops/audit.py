from datetime import datetime
from typing import Any

from app.db.repository import DomainRecordInput
from app.ops.models import AuditEvent, AuditOutcome


def create_audit_event(
    *,
    occurred_at: datetime,
    action: str,
    entity_type: str,
    entity_id: str,
    outcome: AuditOutcome,
    actor: str = "system",
    details: dict[str, Any] | None = None,
) -> AuditEvent:
    if occurred_at.tzinfo is None or occurred_at.utcoffset() is None:
        raise ValueError("occurred_at must be timezone-aware")

    normalized = {
        "action": action.strip(),
        "entity_type": entity_type.strip(),
        "entity_id": entity_id.strip(),
        "actor": actor.strip(),
    }
    if any(not value for value in normalized.values()):
        raise ValueError("audit identifiers are required")

    return AuditEvent(
        occurred_at=occurred_at,
        action=normalized["action"],
        entity_type=normalized["entity_type"],
        entity_id=normalized["entity_id"],
        outcome=outcome,
        actor=normalized["actor"],
        details=dict(details or {}),
    )


def to_domain_record(event: AuditEvent) -> DomainRecordInput:
    return DomainRecordInput(
        record_type="audit",
        symbol=event.entity_id,
        state=event.outcome.value,
        payload=event.model_dump(mode="json"),
    )
