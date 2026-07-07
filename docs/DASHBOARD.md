# Dashboard Summary

The read-only summary endpoint is:

```text
GET /api/v1/dashboard/summary
```

## Behavior

- Aggregates persisted watchlist, setup, flow, plan, lifecycle, and delivery records.
- Returns counts for every typed status, including zero values.
- Uses timezone-aware generation timestamps.
- Performs no writes and enables no live actions.
- Generates no market prices, signals, or synthetic records.
- Ignores non-dashboard records such as audit events and reports the ignored count.
- Preserves records with unknown states under an `UNKNOWN` count and adds a note.

## Data Modes

```text
DATABASE
DATABASE_UNAVAILABLE
NO_STORE
IN_MEMORY
```

`DATABASE` means the query completed. An empty database returns zero totals with the note `No dashboard records are stored.`

`DATABASE_UNAVAILABLE` means the database could not be queried. The endpoint still returns HTTP 200 with zero totals and a sanitized exception type, so infrastructure failure does not become an unhandled API error.

`NO_STORE` remains available through the injectable empty provider for tests or intentionally disconnected deployments.

## Canonical Record Types

```text
watchlist
setup
flow
plan
lifecycle
delivery
```

Only these record types contribute to dashboard totals. Other persisted domain records remain available to their own modules but are not mixed into the funnel summary.
