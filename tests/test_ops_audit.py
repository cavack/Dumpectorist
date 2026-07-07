from datetime import datetime, timezone

import pytest

from app.ops.audit import create_audit_event, to_domain_record
from app.ops.models import AuditOutcome


NOW = datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)


def test_audit_event_converts_to_domain_record():
    event = create_audit_event(
        occurred_at=NOW,
        action="lifecycle.close",
        entity_type="lifecycle",
        entity_id="TEST",
        outcome=AuditOutcome.SUCCESS,
        actor="system",
        details={"reason": "manual"},
    )

    record = to_domain_record(event)

    assert record.record_type == "audit"
    assert record.symbol == "TEST"
    assert record.state == "SUCCESS"
    assert record.payload["action"] == "lifecycle.close"
    assert record.payload["details"] == {"reason": "manual"}


def test_audit_event_rejects_naive_timestamp():
    with pytest.raises(ValueError):
        create_audit_event(
            occurred_at=datetime(2026, 7, 7, 12, 0),
            action="test",
            entity_type="test",
            entity_id="TEST",
            outcome=AuditOutcome.SUCCESS,
        )


def test_audit_event_rejects_blank_identifiers():
    with pytest.raises(ValueError):
        create_audit_event(
            occurred_at=NOW,
            action=" ",
            entity_type="test",
            entity_id="TEST",
            outcome=AuditOutcome.SUCCESS,
        )
