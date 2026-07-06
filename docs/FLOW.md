# Flow Layer

Sprint 5 adds a small flow layer after setup classification.

## Goals

- Prepare setup candidates before later planning layers.
- Keep the layer deterministic and unit tested.
- Keep connectivity out of this layer.
- Keep advanced scoring out of this layer.

## Status Values

```text
READY       Candidate can move forward
WAIT        Candidate should stay pending
INCOMPLETE  Candidate lacks required data
```

## Required Data

```text
current_value
reference_low
reference_high
```

## Flow

```text
SetupCandidate
  -> run_flow
  -> FlowResult
```

## Rules

```text
REVIEW with required data -> READY
WATCH or IGNORE           -> WAIT
missing required data     -> INCOMPLETE
```

## Tests

The test suite covers:

- review candidate with required data
- watch candidate
- ignore candidate
- missing required data
