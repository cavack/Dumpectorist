# Candidate Checks

Sprint 5 adds a small checking layer after setup classification.

## Goals

- Check setup candidates before later planning layers.
- Keep checks deterministic and unit tested.
- Keep exchange connectivity out of this layer.
- Keep advanced scoring out of this layer.

## Status Values

```text
PASS  Candidate can continue
HOLD  Candidate should wait
FAIL  Candidate is missing required data
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
  -> run_candidate_checks
  -> CheckResult
```

## Rules

```text
REVIEW with required data -> PASS
WATCH or IGNORE           -> HOLD
missing required data     -> FAIL
```

## Tests

The test suite covers:

- review candidate with required data
- watch candidate
- ignore candidate
- missing required data
