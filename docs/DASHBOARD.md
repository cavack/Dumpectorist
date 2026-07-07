# Dashboard MVP

Sprint 9 adds a read-only summary endpoint:

```text
GET /api/v1/dashboard/summary
```

## Behavior

- Aggregates watchlist, setup, flow, plan, lifecycle, and delivery records.
- Returns counts for every typed status, including zero values.
- Uses timezone-aware generation timestamps.
- Performs no writes and enables no live actions.
- Generates no market prices, signals, or synthetic records.

## Current Data Mode

The default provider reports `NO_STORE` because persistence is not connected yet. In this mode, the endpoint honestly returns zero totals and a note explaining that no persistence provider is configured.

## Replacement Path

A later persistence provider can return real `OverviewData` without changing the aggregation service or API response model.
