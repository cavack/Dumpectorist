# Runtime and Worker Deployment

The runtime package executes public source adapters in a dedicated worker process. It does not place orders and does not enable live actions.

## Source Kinds

```text
EXECUTION  LBank public execution reference
BENCHMARK  MEXC, Gate, Bybit, Binance USD-M comparison sources
STRUCTURE  closed-candle structure evidence
DISCOVERY  DEX Screener and CoinGecko
```

Every adapter uses the contract:

```python
async def load() -> AdapterPayload
```

A source kind defines storage and downstream permissions. It does not allow one source role to replace another.

## Components

```text
RuntimeSchedule
ScheduledSourceJob
RuntimeOrchestrator
DomainRecordRuntimeStore
RuntimeSupervisor
RuntimeMetrics
DomainRecordRetentionCleaner
build_runtime_jobs
```

## Configuration-driven Registry

`build_runtime_jobs(settings)` creates enabled jobs from environment settings.

Default jobs:

```text
lbank-execution
binance-usdm-benchmark
bybit-linear-benchmark
mexc-usdt-benchmark
gate-usdt-benchmark
bybit-ohlcv-1d
bybit-ohlcv-4h
dex-screener-boosts
coingecko-categories
```

Initial delays are staggered so public endpoints are not contacted at the same instant.

The API may run with every worker source group disabled. The dedicated worker refuses to start when its registry is empty.

## Structure jobs

The OHLCV jobs load closed Daily and 4H Bybit candles with the `STRUCTURE_DATA` role.

They may provide future Daily/4H structure evidence, but they cannot:

- replace LBank execution checks;
- create a setup;
- create an entry, stop, or target;
- create a final signal.

15m and 5m intervals are supported by the candle domain but are not scheduled by default in Sprint 12A.

## Scheduling and Isolation

Each job has:

- interval;
- timeout;
- initial delay;
- unique name;
- explicit source kind.

An in-flight set prevents duplicate concurrent execution of the same job. Different due jobs run concurrently, while each handles its own timeout, adapter error, payload error, and persistence error.

Statuses:

```text
SUCCEEDED
DEGRADED
FAILED
TIMED_OUT
PERSISTENCE_FAILED
```

A failed job cannot cancel another job.

## Persistence

Execution, benchmark, and discovery loads persist atomically as:

```text
execution_snapshot, benchmark_snapshot, discovery_snapshot, or source_diagnostic
source_health
worker_run
```

A fresh OK structure load persists in one transaction:

```text
normalized ohlcv_candles
structure_snapshot
source_health
worker_run
```

A degraded structure load persists:

```text
source_diagnostic
source_health
worker_run
```

It does not insert normalized candles.

If an OK structure payload cannot be deserialized or validated, persistence fails and the transaction rolls back. The runtime reports `PERSISTENCE_FAILED`.

Failed and timed-out loads persist:

```text
source_health
worker_run
```

Decimals in generic domain records are stored as strings. Datetimes must be timezone-aware and are stored as ISO-8601 values. Normalized candle prices and volumes use database numeric columns.

## Supervisor and Telemetry

`RuntimeSupervisor` performs one cycle at each worker tick:

1. run due jobs;
2. update in-memory status counters;
3. emit structured completion logs;
4. emit an error alert after the configured number of consecutive failures;
5. run retention cleanup when due.

A successful or degraded result resets the consecutive hard-failure counter for that job. Durable `worker_run` records provide historical metrics; current counters are available through `RuntimeMetricsSnapshot`.

Retention failure is logged but does not stop source jobs.

## Retention

The default retention period is 30 days. Cleanup applies only to runtime operational records:

```text
execution_snapshot
benchmark_snapshot
discovery_snapshot
source_diagnostic
source_health
worker_run
worker_metrics
```

`structure_snapshot` and normalized `ohlcv_candles` are excluded because they are strategy evidence and future backtest input.

Signal assembly and lifecycle records are also excluded.

## Dedicated Entrypoint

Run the worker directly:

```bash
python -m app.worker
```

The entrypoint:

- creates the configured registry;
- opens the async database engine;
- creates the runtime store and retention cleaner;
- installs `SIGINT` and `SIGTERM` handlers;
- starts the supervisor loop;
- disposes the database engine during shutdown.

Signal handlers set a stop event. The current cycle finishes before the process exits.

## Docker Compose

Compose contains:

```text
migrate
backend-api
runtime-worker
postgres
redis
```

The one-shot `migrate` service runs:

```bash
alembic upgrade head
```

The API and worker start only after migration succeeds. Both use `restart: unless-stopped`; the worker receives a graceful shutdown period.

## Environment Settings

```text
WORKER_TICK_SECONDS
WORKER_SOURCE_TIMEOUT_SECONDS
WORKER_EXECUTION_INTERVAL_SECONDS
WORKER_BENCHMARK_INTERVAL_SECONDS
WORKER_OHLCV_INTERVAL_SECONDS
WORKER_DISCOVERY_INTERVAL_SECONDS
WORKER_CLEANUP_INTERVAL_SECONDS
WORKER_RETENTION_DAYS
WORKER_FAILURE_ALERT_THRESHOLD
WORKER_ENABLE_LBANK
WORKER_ENABLE_BENCHMARKS
WORKER_ENABLE_OHLCV
WORKER_ENABLE_DISCOVERY
WORKER_LBANK_SYMBOL
WORKER_MEXC_SYMBOL
WORKER_GATE_SYMBOL
WORKER_BYBIT_SYMBOL
WORKER_BINANCE_SYMBOL
WORKER_OHLCV_SYMBOL
WORKER_OHLCV_LIMIT
```

All intervals, limits, and enabled-source symbols are validated by Pydantic settings.

## Safety Rules

- Public endpoints only.
- No order-placement interface.
- No synthetic fallback values.
- Open candles are excluded from closed evidence.
- LBank remains the execution reference.
- Benchmark, structure, and discovery roles remain restricted.
- Empty worker registries fail fast in the worker process only.
- Generic runtime cleanup cannot delete normalized candles, structure evidence, signal assembly, or lifecycle records.
- Runtime completion cannot create a final signal by itself.
