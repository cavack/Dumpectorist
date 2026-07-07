# Persistence Foundation

The persistence layer contains generic domain records plus normalized strategy evidence where query shape and uniqueness require dedicated tables.

## Domain records

Sprint 10A introduced:

- SQLAlchemy declarative base;
- generic domain-record model;
- async engine and session factory;
- validated repository;
- Alembic configuration;
- initial migration;
- integration and migration tests.

Fields:

```text
id
record_type
symbol
state
payload
created_at
updated_at
expires_at
```

Generic records store snapshots, diagnostics, health, worker runs, assembly records, lifecycle records, and operational events.

## Normalized OHLCV candles

Sprint 12A adds the dedicated `ohlcv_candles` table because candles require deterministic uniqueness, chronological queries, precise numeric columns, idempotent ingestion, and future backtest reuse.

Fields:

```text
id
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

Unique identity:

```text
source + symbol + interval + open_time
```

Indexes:

```text
symbol + interval + open_time
source + close_time
```

The candle repository supports:

- idempotent batch upsert;
- update of corrected historical rows;
- chronological recent-candle queries;
- UTC normalization when a development SQLite database returns naive datetime objects.

## Atomic runtime persistence

A successful structure job persists normalized candles and generic runtime records in one transaction.

```text
ohlcv_candles
structure_snapshot
source_health
worker_run
```

If candle payload validation or upsert fails, the transaction is not committed and the runtime returns `PERSISTENCE_FAILED`.

Degraded structure payloads persist diagnostics and runtime state only. They do not insert candle rows.

## Retention

The generic runtime-retention cleaner targets operational record types only. It does not delete normalized candles, structure snapshots, signal assembly records, or lifecycle records.

Any future candle-retention policy must be explicit, interval-aware, separately configured, and tested before activation.

## Migration chain

```text
20260707_0001  domain_records
20260707_0002  ohlcv_candles
```

Commands:

```bash
alembic upgrade head
alembic downgrade 20260707_0001
alembic upgrade head
alembic downgrade base
```

Tests use a temporary SQLite database. The application database URL continues to come from settings.
