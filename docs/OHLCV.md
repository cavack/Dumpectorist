# Real Closed-Candle OHLCV Foundation

Sprint 12A introduces the real candle-data layer required before the Daily/4H structure engine can replace manual structure evidence.

## Source role

The initial source is the public Bybit V5 kline endpoint. Its role is strictly `STRUCTURE_DATA`.

Allowed uses:

- Daily and 4H structure evidence;
- future 15m setup confirmation;
- future 5m timing evidence;
- historical candle reconstruction;
- volume and turnover context.

Forbidden uses:

- executable entry price;
- LBank spread or depth replacement;
- final stop or target validation;
- setup, plan, or final-signal creation.

LBank remains the execution reference.

## Supported intervals

```text
1d   higher-timeframe direction and major structure
4h   primary structure and setup evidence
15m  future confirmation evidence
5m   future timing evidence
```

The runtime registry enables Daily and 4H jobs in this sprint. The domain contract supports all four locked intervals.

## Closed-candle guarantee

The adapter calculates each candle close time from its open time and interval. A row whose close time is later than the local fetch timestamp is treated as currently forming and is discarded.

A valid batch guarantees:

- timezone-aware timestamps;
- interval-consistent duration;
- finite positive OHLC values;
- non-negative volume and turnover;
- consistent high/low relationships;
- one source, role, category, symbol, and interval;
- unique and strictly chronological open times;
- closed candles only.

No replacement candle is generated when the source is incomplete or unavailable.

## Freshness

Freshness is evaluated from the latest closed candle.

States:

```text
OK
EMPTY
STALE
FUTURE
```

The default stale threshold is two interval durations. This is a safety default and may be calibrated only from documented dry-run evidence.

A non-OK freshness result produces a degraded payload and cannot insert normalized candle rows.

## Persistence

Normalized candles are stored in `ohlcv_candles`.

Unique identity:

```text
source + symbol + interval + open_time
```

Stored fields:

```text
source
role
category
symbol
interval
open_time
close_time
open_price
high_price
low_price
close_price
volume
turnover
created_at
updated_at
```

The repository performs idempotent batch upsert:

- new candles are inserted;
- unchanged candles remain unchanged;
- corrected historical candles update the matching row;
- duplicates are not created.

Recent candles are returned chronologically.

## Runtime jobs

Default jobs:

```text
bybit-ohlcv-1d
bybit-ohlcv-4h
```

Both use `SourceJobKind.STRUCTURE` and are staggered to avoid simultaneous requests.

Configuration:

```text
WORKER_ENABLE_OHLCV
WORKER_OHLCV_INTERVAL_SECONDS
WORKER_OHLCV_SYMBOL
WORKER_OHLCV_LIMIT
```

For an OK structure payload, one transaction persists:

```text
normalized ohlcv_candles
structure_snapshot
source_health
worker_run
```

For a degraded structure payload, no normalized candle is inserted. The runtime stores:

```text
source_diagnostic
source_health
worker_run
```

Malformed OK payloads fail persistence and roll back the entire transaction.

## Retention

Normalized candles are strategy evidence and future backtest input. They are not part of the generic runtime operational-retention list.

Any future candle-retention policy must be explicit, interval-aware, documented, and independently tested.

## Migration

Migration chain:

```text
20260707_0001 domain_records
20260707_0002 ohlcv_candles
```

Rollback of Sprint 12A data schema:

```bash
alembic downgrade 20260707_0001
```

Disabling runtime ingestion does not require a database rollback:

```text
WORKER_ENABLE_OHLCV=false
```

## Safety boundary

This sprint does not implement:

- support zones;
- Daily/4H structure-break classification;
- successful reclaim;
- failed pullback;
- entry, stop, targets, scoring, or final signals.

Sprint 12B consumes these persisted candles to derive timestamped support and structure evidence.
