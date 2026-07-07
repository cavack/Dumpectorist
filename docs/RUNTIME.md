# Runtime and Worker Deployment

The runtime package executes public source adapters in a dedicated worker process. It does not place orders and does not enable live actions.

## Source Kinds

```text
EXECUTION  LBank public execution reference
BENCHMARK  MEXC, Gate, Bybit, Binance USD-M
DISCOVERY  DEX Screener and CoinGecko
```

Every adapter uses the existing contract:

```python
async def load() -> AdapterPayload
```

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

`build_runtime_jobs(settings)` creates the enabled jobs from environment settings.

Default jobs:

```text
lbank-execution
binance-usdm-benchmark
bybit-linear-benchmark
mexc-usdt-benchmark
gate-usdt-benchmark
dex-screener-boosts
coingecko-categories
```

Initial delays are staggered so all public endpoints are not contacted at the same instant.

The API may run with every worker source group disabled. The dedicated worker refuses to start when its registry is empty.

## Scheduling and Isolation

Each job has:

- interval
- timeout
- initial delay
- unique name
- explicit source kind

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

Successful or degraded loads persist atomically:

```text
execution_snapshot, benchmark_snapshot, or discovery_snapshot
source_health
worker_run
```

Failed and timed-out loads persist:

```text
source_health
worker_run
```

Decimals are stored as strings. Datetimes must be timezone-aware and are stored as ISO-8601 values.

## Supervisor and Telemetry

`RuntimeSupervisor` performs one cycle at each worker tick:

1. run due jobs
2. update in-memory status counters
3. emit structured completion logs
4. emit an error alert after the configured number of consecutive failures
5. run retention cleanup when due

A successful or degraded result resets the consecutive hard-failure counter for that job. Durable `worker_run` records provide historical metrics; current counters are available through `RuntimeMetricsSnapshot`.

Retention failure is logged but does not stop source jobs.

## Retention

The default retention period is 30 days. Cleanup applies only to runtime operational records:

```text
execution_snapshot
benchmark_snapshot
discovery_snapshot
source_health
worker_run
```

Signal assembly and lifecycle records are not included in runtime cleanup.

## Dedicated Entrypoint

Run the worker directly:

```bash
python -m app.worker
```

The entrypoint:

- creates the configured registry
- opens the async database engine
- creates the runtime store and retention cleaner
- installs `SIGINT` and `SIGTERM` handlers
- starts the supervisor loop
- disposes the database engine during shutdown

Signal handlers set a stop event. The current cycle finishes before the process exits.

## Docker Compose

Compose contains four operational services:

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

The API and worker start only after migration succeeds. Both use `restart: unless-stopped`; the worker receives a 20-second graceful shutdown period.

## Environment Settings

```text
WORKER_TICK_SECONDS
WORKER_SOURCE_TIMEOUT_SECONDS
WORKER_EXECUTION_INTERVAL_SECONDS
WORKER_BENCHMARK_INTERVAL_SECONDS
WORKER_DISCOVERY_INTERVAL_SECONDS
WORKER_CLEANUP_INTERVAL_SECONDS
WORKER_RETENTION_DAYS
WORKER_FAILURE_ALERT_THRESHOLD
WORKER_ENABLE_LBANK
WORKER_ENABLE_BENCHMARKS
WORKER_ENABLE_DISCOVERY
WORKER_LBANK_SYMBOL
WORKER_MEXC_SYMBOL
WORKER_GATE_SYMBOL
WORKER_BYBIT_SYMBOL
WORKER_BINANCE_SYMBOL
```

All intervals and limits are validated by Pydantic settings.

## Safety Rules

- Public endpoints only.
- No order-placement interface.
- No synthetic fallback values.
- LBank remains the execution reference.
- Benchmark and discovery roles remain restricted.
- Empty worker registries fail fast in the worker process only.
- Database cleanup cannot delete signal assembly records.
- Runtime completion cannot create a final signal by itself.
