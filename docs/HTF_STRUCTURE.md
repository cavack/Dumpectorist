# Daily/4H Structure Engine

## Scope

Sprint 12B derives explainable higher-timeframe support zones and structure events from persisted closed candles.

The engine is evidence-only. It does not create entries, stops, targets, scores, final signals, or orders. LBank remains the execution reference and later hard gates still control `SHORT_READY`.

## Input contract

- Daily (`1d`) or four-hour (`4h`) candles only.
- One source, symbol, and interval per batch.
- Strict chronological order.
- Closed candles only; the OHLCV foundation rejects open candles before analysis.
- No future-candle access.

## Support-zone derivation

A pivot low is confirmed only after both its left and right windows are closed. This is the no-look-ahead boundary.

Default rules:

```text
pivot_left                  2 candles
pivot_right                 2 candles
minimum_touches             2
minimum_touch_separation    2 candles
cluster_tolerance           75 bps
zone_padding                20 bps
maximum_zone_width          180 bps
minimum_rejection           25 bps
maximum_zones               5
```

Processing sequence:

1. Find confirmed pivot lows.
2. Enforce minimum separation between adjacent pivots.
3. Cluster pivots by median-price distance.
4. Require at least two touches.
5. Pad the observed low range into a price zone.
6. Reject zones wider than the configured maximum.
7. Calculate touch count, rejection count, recency, and strength.
8. Rank zones deterministically.

The zone identifier is deterministic and includes source, symbol, interval, bounds, confirmation time, and evidence candle times.

## Zone strength

Initial deterministic score:

```text
25
+ 12 per touch
+ 6 per rejection
+ up to 15 recency points
```

The score is capped at 100. These are initial engineering defaults, not trading-performance claims. Calibration belongs to the later dry-run and backtest phase.

## Structure events

Default rules:

```text
minimum_break_distance      10 bps below zone low
minimum_break_body_fraction 0.45
fake_break_window           3 candles
maximum_zone_age            100 candles
volume_lookback             5 candles
```

Event states:

```text
PENDING_BREAK
CONFIRMED_BREAK
FAKE_BREAK
RECLAIMED
INVALIDATED
```

Behavior:

- A close below the zone with incomplete distance/body confirmation emits one `PENDING_BREAK`.
- A close below the zone meeting both distance and body thresholds emits `CONFIRMED_BREAK`.
- A close back above the zone within the fake-break window emits `FAKE_BREAK`.
- A later close above the zone emits `RECLAIMED`.
- A zone that ages beyond the configured limit without breaking emits `INVALIDATED`.
- Reclaim and fake-break events link to the confirmed event they invalidate.

Event identifiers are deterministic from the zone, candle timestamps, and state.

## Derived evidence

The latest primary-zone state maps to timeframe evidence:

```text
no zone             -> INSUFFICIENT
zone, no event       -> INTACT
PENDING_BREAK        -> WATCH
CONFIRMED_BREAK      -> DAMAGED
FAKE_BREAK           -> RECLAIMED
RECLAIMED            -> RECLAIMED
INVALIDATED          -> INVALIDATED
```

Daily and 4H evidence remain separate. Production assembly consumes repository-derived evidence rather than manually supplied higher-timeframe booleans.

## Persistence

Normalized tables:

```text
support_zones
structure_events
```

Each record preserves:

- source, symbol, and interval;
- evidence and observation timestamps;
- zone bounds;
- event state;
- deterministic identifier;
- reason codes;
- invalidation link where applicable.

Upsert is idempotent. Reprocessing the same closed-candle history does not create duplicate zones or events.

## Runtime transaction boundary

After a fresh successful Daily/4H candle load, one transaction persists:

```text
ohlcv_candles
support_zones
structure_events
structure_snapshot
source_health
worker_run
```

If candle validation, structure analysis, or persistence fails, the transaction rolls back and the job reports `PERSISTENCE_FAILED`.

A degraded candle load does not run structure analysis and does not insert normalized structure evidence.

## Retention

Support zones and structure events are strategy evidence and future backtest input. Generic operational retention must not delete them.

## Safety boundaries

- No open-candle evidence.
- No look-ahead pivot confirmation.
- No benchmark source may replace LBank execution validation.
- `DAMAGED` structure alone cannot create `SHORT_READY`.
- Successful reclaim behavior for setup cancellation is completed in Sprint 12C.
- Current thresholds are configuration candidates and must be calibrated using real captured data and setup-based backtests.

## Rollback

Application rollback:

1. Disable OHLCV structure jobs if immediate isolation is required.
2. Revert the Sprint 12B application commit.
3. Preserve normalized evidence unless a database rollback is explicitly required.

Database rollback:

```bash
alembic downgrade 20260707_0002
```

This removes `support_zones` and `structure_events`. Export evidence first when it must be preserved.
