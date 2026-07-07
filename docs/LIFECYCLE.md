# Lifecycle Tracking

Sprint 8 adds deterministic lifecycle tracking and expiry handling after plan creation.

## States

```text
PENDING  Plan is held and has not been activated
ACTIVE   Plan is active inside its validity window
EXPIRED  Validity window has ended
CLOSED   Record was closed manually
```

## Flow

```text
PlanDraft
  -> create_lifecycle
  -> LifecycleRecord
  -> activate_lifecycle / advance_lifecycle / close_lifecycle
```

## Rules

- Ready plans start ACTIVE.
- Held plans start PENDING.
- Every record receives an expiry timestamp from a positive TTL.
- Records become EXPIRED when the current time reaches `expires_at`.
- EXPIRED and CLOSED records are terminal and do not transition again.
- All timestamps must be timezone-aware.
- Time cannot move backwards relative to `updated_at`.

## Scope Limits

This sprint does not add database persistence, schedulers, or live actions. All transitions are deterministic pure service calls over immutable records.
