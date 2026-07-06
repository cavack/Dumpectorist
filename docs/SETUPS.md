# Setup Classification

Sprint 4 connects structure snapshots to a small setup classification layer.

## Goals

- Convert structure snapshots into setup candidates.
- Keep classification deterministic and unit tested.
- Keep advanced scoring out of this layer.
- Keep live execution out of this layer.

## Labels

```text
IGNORE  Snapshot does not need attention
WATCH   Snapshot should stay on watch
REVIEW  Snapshot should move to review
```

## Flow

```text
StructureSnapshot
  -> classify_snapshot
  -> SetupCandidate
```

## Rules

```text
NEUTRAL -> IGNORE
WEAK    -> WATCH
ALERT   -> REVIEW
```

## Tests

The test suite covers:

- neutral snapshots
- weak snapshots
- alert snapshots
- candidate data preservation
