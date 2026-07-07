# Runtime Orchestration

The runtime package schedules public benchmark and discovery adapters, isolates each job, and persists source payloads and health through the existing `domain_records` table.

It does not place orders and does not enable live actions.

## Components

```text
RuntimeSchedule
ScheduledSourceJob
RuntimeOrchestrator
DomainRecordRuntimeStore
```

Helper functions create correctly typed jobs:

```text
benchmark_job(...)
discovery_job(...)
```

Every adapter must expose its existing public contract:

```python
async def load() -> AdapterPayload
```

This allows LBank-independent benchmark adapters and discovery adapters to use the same scheduler without sharing market-specific parsing logic.

## Scheduling Rules

Each job has:

- `interval_seconds`
- `timeout_seconds`
- `initial_delay_seconds`
- a unique job name
- a `BENCHMARK` or `DISCOVERY` kind

The first due time is calculated when the scheduler starts observing the job. Before a due job begins, its next run time is moved forward by one interval. An in-flight set prevents a second scheduler cycle from starting the same job concurrently.

Different jobs run concurrently through `asyncio.gather`, while every job handles its own timeout, adapter error, and persistence error.

## Worker Statuses

```text
SUCCEEDED
DEGRADED
FAILED
TIMED_OUT
PERSISTENCE_FAILED
```

Mapping from adapter health:

```text
AdapterState.OK        -> SUCCEEDED
AdapterState.DEGRADED  -> DEGRADED
AdapterState.DOWN      -> FAILED
```

A degraded adapter payload is still persisted because it contains useful health and diagnostic context. It is not converted into valid market data.

## Failure Isolation

A failure in one adapter does not cancel other due jobs.

Handled failure classes include:

- adapter exception
- adapter timeout
- malformed adapter payload
- adapter and payload name mismatch
- database persistence exception

Timeout cancels only the timed-out adapter coroutine. In-flight state is cleared in a `finally` block.

## Persistence Records

Successful and degraded adapter loads are stored atomically as:

```text
benchmark_snapshot or discovery_snapshot
source_health
worker_run
```

A failed or timed-out adapter stores:

```text
source_health
worker_run
```

The snapshot symbol is selected from explicit payload fields in this order:

```text
symbol
query
job name
```

Decimals are stored as strings and timezone-aware datetimes are stored as ISO-8601 values. Unknown Python object types are rejected instead of being silently stringified.

No new migration is required because runtime records use the existing generic `DomainRecord` model and its `record_type`, `symbol`, `state`, and JSON payload fields.

## Example

```python
import asyncio

from app.adapters.binance_futures import BinanceUsdMAdapter
from app.adapters.coingecko import CoinGeckoDiscoveryAdapter, CoinGeckoFeed
from app.db.session import Database
from app.runtime import (
    DomainRecordRuntimeStore,
    RuntimeOrchestrator,
    benchmark_job,
    discovery_job,
)


database = Database("postgresql+asyncpg://app:change_me@postgres:5432/app")
store = DomainRecordRuntimeStore(database.session_factory)

jobs = [
    benchmark_job(
        BinanceUsdMAdapter(symbol="BTCUSDT"),
        interval_seconds=5,
        timeout_seconds=3,
    ),
    discovery_job(
        CoinGeckoDiscoveryAdapter(feed=CoinGeckoFeed.CATEGORIES),
        interval_seconds=300,
        timeout_seconds=10,
        initial_delay_seconds=15,
    ),
]

runtime = RuntimeOrchestrator(jobs, store=store)
stop_event = asyncio.Event()
await runtime.run_forever(stop_event, tick_seconds=1)
```

The runtime should be launched as a dedicated worker process. API startup wiring, deployment supervision, and retention cleanup remain separate operational tasks.

## Safety Rules

- Public adapter methods only.
- No order-placement interface.
- No synthetic fallback values.
- Unique job names are mandatory.
- Naive datetimes are rejected.
- Persistence errors are reported, not hidden.
- Discovery records remain `DISCOVERY_ONLY`.
- Benchmark records remain `BENCHMARK_ONLY`.
- Runtime completion does not create a setup, plan, or final signal.
