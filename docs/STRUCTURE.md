# Structure Models

Sprint 3 adds a deterministic structure model layer above watchlist entries.

## Goals

- Convert watchlist entries into structure inputs.
- Classify simple value position against a reference range.
- Keep the analyzer deterministic and unit tested.
- Keep scoring and execution out of this layer.

## States

```text
NEUTRAL  Current value is in the upper part of the range
WEAK     Current value is in the lower part of the range
ALERT    Current value is outside the reference range
```

## Flow

```text
WatchlistEntry
  -> StructureInput
  -> analyze_structure
  -> StructureSnapshot
```

## Validation

The analyzer rejects invalid ranges where `reference_low >= reference_high`.

## Tests

The test suite covers:

- neutral state
- weak state
- alert state
- invalid reference ranges
- conversion from watchlist entries
