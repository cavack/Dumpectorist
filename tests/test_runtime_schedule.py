import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from app.adapters.models import AdapterHealth, AdapterPayload, AdapterState
from app.runtime.models import (
    RuntimeSchedule,
    ScheduledSourceJob,
    SourceJobKind,
    WorkerRunStatus,
)
from app.runtime.scheduler import RuntimeOrchestrator
from app.runtime.store import InMemoryRuntimeStore


NOW = datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)


class StaticAdapter:
    def __init__(self, name: str, state: AdapterState = AdapterState.OK) -> None:
        self.name = name
        self.state = state
        self.calls = 0

    async def load(self) -> AdapterPayload:
        self.calls += 1
        return AdapterPayload(
            name=self.name,
            data={"symbol": "BTCUSDT", "value": "100"},
            health=AdapterHealth(name=self.name, state=self.state, latency_ms=5),
        )


class ErrorAdapter:
    name = "error-adapter"

    async def load(self) -> AdapterPayload:
        raise RuntimeError("fixture error")


class SlowAdapter:
    name = "slow-adapter"

    async def load(self) -> AdapterPayload:
        await asyncio.sleep(0.05)
        return AdapterPayload(
            name=self.name,
            data={"symbol": "BTCUSDT"},
            health=AdapterHealth(name=self.name, state=AdapterState.OK),
        )


class BlockingAdapter:
    name = "blocking-adapter"

    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.calls = 0

    async def load(self) -> AdapterPayload:
        self.calls += 1
        self.started.set()
        await self.release.wait()
        return AdapterPayload(
            name=self.name,
            data={"query": "universe"},
            health=AdapterHealth(name=self.name, state=AdapterState.OK),
        )


def make_job(
    name: str,
    adapter,
    *,
    interval: float = 60,
    timeout: float = 1,
    initial_delay: float = 0,
) -> ScheduledSourceJob:
    return ScheduledSourceJob(
        name=name,
        kind=SourceJobKind.BENCHMARK,
        adapter=adapter,
        schedule=RuntimeSchedule(
            interval_seconds=interval,
            timeout_seconds=timeout,
            initial_delay_seconds=initial_delay,
        ),
    )


@pytest.mark.asyncio
async def test_one_error_does_not_cancel_other_job():
    store = InMemoryRuntimeStore()
    orchestrator = RuntimeOrchestrator(
        [
            make_job("healthy", StaticAdapter("healthy-adapter")),
            make_job("error", ErrorAdapter()),
        ],
        store=store,
        clock=lambda: NOW,
    )

    outcomes = await orchestrator.run_due(NOW)

    assert [item.status for item in outcomes] == [
        WorkerRunStatus.SUCCEEDED,
        WorkerRunStatus.FAILED,
    ]
    assert len(store.payload_runs) == 1
    assert len(store.failure_runs) == 1


@pytest.mark.asyncio
async def test_timeout_is_isolated():
    store = InMemoryRuntimeStore()
    orchestrator = RuntimeOrchestrator(
        [
            make_job("slow", SlowAdapter(), timeout=0.01),
            make_job("fast", StaticAdapter("fast-adapter")),
        ],
        store=store,
        clock=lambda: NOW,
    )

    outcomes = await orchestrator.run_due(NOW)

    assert outcomes[0].status == WorkerRunStatus.TIMED_OUT
    assert outcomes[1].status == WorkerRunStatus.SUCCEEDED
    assert len(store.failure_runs) == 1
    assert len(store.payload_runs) == 1


@pytest.mark.asyncio
async def test_initial_delay_and_interval_are_enforced():
    adapter = StaticAdapter("scheduled-adapter")
    orchestrator = RuntimeOrchestrator(
        [make_job("scheduled", adapter, interval=30, initial_delay=10)],
        clock=lambda: NOW,
    )

    assert await orchestrator.run_due(NOW) == ()
    assert orchestrator.next_run_at("scheduled") == NOW + timedelta(seconds=10)

    first = await orchestrator.run_due(NOW + timedelta(seconds=10))
    assert len(first) == 1
    assert orchestrator.next_run_at("scheduled") == NOW + timedelta(seconds=40)

    assert await orchestrator.run_due(NOW + timedelta(seconds=39)) == ()
    second = await orchestrator.run_due(NOW + timedelta(seconds=40))
    assert len(second) == 1
    assert adapter.calls == 2


@pytest.mark.asyncio
async def test_in_flight_job_is_not_started_twice():
    adapter = BlockingAdapter()
    orchestrator = RuntimeOrchestrator(
        [make_job("blocking", adapter)],
        clock=lambda: NOW,
    )

    first_cycle = asyncio.create_task(orchestrator.run_due(NOW))
    await adapter.started.wait()

    assert await orchestrator.run_due(NOW) == ()

    adapter.release.set()
    first_outcomes = await first_cycle
    assert first_outcomes[0].status == WorkerRunStatus.SUCCEEDED
    assert adapter.calls == 1


def test_runtime_schedule_validation():
    with pytest.raises(ValueError):
        RuntimeSchedule(interval_seconds=0, timeout_seconds=1)
    with pytest.raises(ValueError):
        RuntimeSchedule(interval_seconds=1, timeout_seconds=0)
    with pytest.raises(ValueError):
        RuntimeOrchestrator(
            [
                make_job("duplicate", StaticAdapter("one")),
                make_job("duplicate", StaticAdapter("two")),
            ]
        )
