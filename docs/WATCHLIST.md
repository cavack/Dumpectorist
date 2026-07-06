# Watchlist Workflow

Sprint 2 adds the first workflow layer above adapters.

## Goals

- Convert adapter payloads into typed watchlist entries.
- Keep workflow decisions separate from external source loading.
- Pause entries when source health is not usable.
- Reject payloads that do not contain required fields.
- Keep advanced scoring out of this layer.

## Required Input Fields

```text
symbol
price
```

## Stages

```text
NEW        Created but not yet processed
WATCHING   Accepted for active monitoring
REVIEWING  Moved into manual or downstream review
PAUSED     Source health or payload state prevents active use
```

## Flow

```text
AdapterPayload
  -> validate required fields
  -> check AdapterHealth
  -> create WatchlistEntry
  -> optionally move active entries to REVIEWING
```

## Tests

The test suite covers:

- usable payloads
- unusable source health
- missing required fields
- review movement
- paused entry behavior
