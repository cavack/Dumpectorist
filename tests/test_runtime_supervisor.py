import logging
from datetime import datetime, timedelta, timezone

import pytest

from app.adapters.models import AdapterState
from app.runtime.models import SourceJobKind, WorkerRunOutcome, WorkerRunStatus
from app.runtime.retention import RetentionResult
from app.runtime.supervisor import RuntimeSupervisor
from app.runtime.telemetry import RuntimeMetrics


NOW = datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)


def outcome(
    status: WorkerRunStatus,
    *,
    job_name: str = "fixture-job",
    message: str = "fixture",
) -> WorkerRunOutcome:
    return WorkerRunOutcome(
        job_name=job_name,
        kind=SourceJobKind.BENCHMARK,
        status=status,
        started_at=NOW,
        finished_at=NOW + timedelta(milliseconds=10),
        adapter_state=(
            AdapterState.OK
            if status == WorkerRunStatus.SUCCEEDED
            else AdapterState.DOWN
        ),
        message=message,
    )


class FixtureOrchestrator:
    def __init__(self, cycles: list[tuple[WorkerRunOutcome, ...]]) -> None:
        self.cycles = cycles
        self.calls: list[datetime] = []

    async def run_due(self, now: datetime) -> tuple[WorkerRunOutcome, ...]:
        self.calls.append(now)
        return self.cycles.pop(0) if self.cycles else ()


class FixtureCleaner:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[datetime] = []

    async def cleanup(self, *, now: datetime) -> RetentionResult:
        self.calls.append(now)
        if self.fail:
            raise RuntimeError("cleanup fixture")
        return RetentionResult(
            cutoff=now - timedelta(days=30),
            deleted_records=2,
        )


def test_metrics_alert_after_threshold_and_reset_after_success():
    metrics = RuntimeMetrics()

    first = metrics.observe(
        (outcome(WorkerRunStatus.FAILED),),
        failure_alert_threshold=2,
    )
    second = metrics.observe(
        (outcome(WorkerRunStatus.TIMED_OUT),),
        failure_alert_threshold=2,
    )
    reset = metrics.observe(
        (outcome(WorkerRunStatus.SUCCEEDED),),
        failure_alert_threshold=2,
    )

    assert first == ()
    assert len(second) == 1
    assert second[0].consecutive_failures == 2
    assert second[0].status == WorkerRunStatus.TIMED_OUT
    assert reset == ()
    assert metrics.consecutive_failures["fixture-job"] == 0

    snapshot = metrics.snapshot(now=NOW)
    assert snapshot.total_runs == 3
    assert snapshot.status_counts == {
        "FAILED": 1,
        "TIMED_OUT": 1,
        "SUCCEEDED": 1,
    }
    assert snapshot.last_status == {"fixture-job": "SUCCEEDED"}


@pytest.mark.asyncio
async def test_supervisor_runs_jobs_alerts_and_retention_on_schedule(caplog):
    orchestrator = FixtureOrchestrator(
        [
            (outcome(WorkerRunStatus.FAILED),),
            (outcome(WorkerRunStatus.FAILED),),
            (),
        ]
    )
    cleaner = FixtureCleaner()
    supervisor = RuntimeSupervisor(
        orchestrator,
        cleaner=cleaner,
        cleanup_interval_seconds=60,
        failure_alert_threshold=2,
        logger=logging.getLogger("test-runtime-supervisor"),
    )

    with caplog.at_level(logging.INFO):
        first = await supervisor.run_cycle(now=NOW)
        second = await supervisor.run_cycle(now=NOW + timedelta(seconds=10))
        third = await supervisor.run_cycle(now=NOW + timedelta(seconds=60))

    assert first.retention is not None
    assert first.retention.deleted_records == 2
    assert second.retention is None
    assert len(second.alerts) == 1
    assert third.retention is not None
    assert cleaner.calls == [NOW, NOW + timedelta(seconds=60)]
    assert "runtime_failure_alert" in caplog.text
    assert "runtime_retention_complete" in caplog.text


@pytest.mark.asyncio
async def test_cleanup_failure_does_not_stop_cycle(caplog):
    orchestrator = FixtureOrchestrator([(outcome(WorkerRunStatus.SUCCEEDED),)])
    cleaner = FixtureCleaner(fail=True)
    supervisor = RuntimeSupervisor(
        orchestrator,
        cleaner=cleaner,
        logger=logging.getLogger("test-cleanup-failure"),
    )

    with caplog.at_level(logging.ERROR):
        cycle = await supervisor.run_cycle(now=NOW)

    assert cycle.outcomes[0].status == WorkerRunStatus.SUCCEEDED
    assert cycle.retention is None
    assert "runtime_retention_failed" in caplog.text


def test_supervisor_and_metrics_validation():
    orchestrator = FixtureOrchestrator([])
    with pytest.raises(ValueError):
        RuntimeSupervisor(orchestrator, tick_seconds=0)
    with pytest.raises(ValueError):
        RuntimeSupervisor(orchestrator, cleanup_interval_seconds=0)
    with pytest.raises(ValueError):
        RuntimeSupervisor(orchestrator, failure_alert_threshold=0)
    with pytest.raises(ValueError):
        RuntimeMetrics().snapshot(now=datetime(2026, 7, 7, 12, 0))
