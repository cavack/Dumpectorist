import asyncio
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta, timezone

from app.adapters.models import AdapterPayload, AdapterState
from app.runtime.models import (
    ScheduledSourceJob,
    WorkerRunOutcome,
    WorkerRunStatus,
)
from app.runtime.store import NullRuntimeStore, RuntimeStore


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _error_message(error: Exception) -> str:
    detail = str(error).strip()
    if detail:
        return f"{type(error).__name__}: {detail}"[:500]
    return type(error).__name__


def _status_for_payload(payload: AdapterPayload) -> WorkerRunStatus:
    if payload.health.state == AdapterState.OK:
        return WorkerRunStatus.SUCCEEDED
    if payload.health.state == AdapterState.DEGRADED:
        return WorkerRunStatus.DEGRADED
    return WorkerRunStatus.FAILED


class RuntimeOrchestrator:
    def __init__(
        self,
        jobs: Sequence[ScheduledSourceJob],
        *,
        store: RuntimeStore | None = None,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        normalized_jobs = tuple(jobs)
        names = [job.name for job in normalized_jobs]
        if len(names) != len(set(names)):
            raise ValueError("runtime job names must be unique")

        self._jobs = normalized_jobs
        self._job_by_name = {job.name: job for job in normalized_jobs}
        self._store = store or NullRuntimeStore()
        self._clock = clock
        self._next_run_at: dict[str, datetime | None] = {
            job.name: None for job in normalized_jobs
        }
        self._in_flight: set[str] = set()
        self._state_lock = asyncio.Lock()

    @property
    def jobs(self) -> tuple[ScheduledSourceJob, ...]:
        return self._jobs

    def next_run_at(self, job_name: str) -> datetime | None:
        if job_name not in self._job_by_name:
            raise KeyError(job_name)
        return self._next_run_at[job_name]

    async def run_due(self, now: datetime) -> tuple[WorkerRunOutcome, ...]:
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("now must be timezone-aware")

        due_jobs: list[ScheduledSourceJob] = []
        async with self._state_lock:
            for job in self._jobs:
                scheduled_at = self._next_run_at[job.name]
                if scheduled_at is None:
                    scheduled_at = now + timedelta(
                        seconds=job.schedule.initial_delay_seconds
                    )
                    self._next_run_at[job.name] = scheduled_at

                if scheduled_at > now or job.name in self._in_flight:
                    continue

                self._in_flight.add(job.name)
                self._next_run_at[job.name] = now + timedelta(
                    seconds=job.schedule.interval_seconds
                )
                due_jobs.append(job)

        if not due_jobs:
            return ()

        outcomes = await asyncio.gather(
            *(self._run_job(job, scheduled_now=now) for job in due_jobs),
        )
        return tuple(outcomes)

    async def run_forever(
        self,
        stop_event: asyncio.Event,
        *,
        tick_seconds: float = 1.0,
    ) -> None:
        if tick_seconds <= 0:
            raise ValueError("tick_seconds must be positive")

        while not stop_event.is_set():
            await self.run_due(self._aware_clock())
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=tick_seconds)
            except TimeoutError:
                continue

    async def _run_job(
        self,
        job: ScheduledSourceJob,
        *,
        scheduled_now: datetime,
    ) -> WorkerRunOutcome:
        started_at = scheduled_now
        try:
            try:
                started_at = self._clock_not_before(scheduled_now)
                payload = await asyncio.wait_for(
                    job.adapter.load(),
                    timeout=job.schedule.timeout_seconds,
                )
                self._validate_payload(job, payload)
                finished_at = self._safe_clock_not_before(started_at)
                outcome = WorkerRunOutcome(
                    job_name=job.name,
                    kind=job.kind,
                    status=_status_for_payload(payload),
                    started_at=started_at,
                    finished_at=finished_at,
                    adapter_state=payload.health.state,
                    message=payload.health.message,
                )
                return await self._persist_payload(job, payload, outcome)
            except TimeoutError:
                finished_at = self._safe_clock_not_before(started_at)
                outcome = WorkerRunOutcome(
                    job_name=job.name,
                    kind=job.kind,
                    status=WorkerRunStatus.TIMED_OUT,
                    started_at=started_at,
                    finished_at=finished_at,
                    adapter_state=AdapterState.DOWN,
                    message="source load timed out",
                )
                return await self._persist_failure(job, outcome)
            except Exception as error:
                finished_at = self._safe_clock_not_before(started_at)
                outcome = WorkerRunOutcome(
                    job_name=job.name,
                    kind=job.kind,
                    status=WorkerRunStatus.FAILED,
                    started_at=started_at,
                    finished_at=finished_at,
                    adapter_state=AdapterState.DOWN,
                    message=_error_message(error),
                )
                return await self._persist_failure(job, outcome)
        finally:
            async with self._state_lock:
                self._in_flight.discard(job.name)

    async def _persist_payload(
        self,
        job: ScheduledSourceJob,
        payload: AdapterPayload,
        outcome: WorkerRunOutcome,
    ) -> WorkerRunOutcome:
        try:
            await self._store.persist_payload(job, payload, outcome)
        except Exception as error:
            return WorkerRunOutcome(
                job_name=job.name,
                kind=job.kind,
                status=WorkerRunStatus.PERSISTENCE_FAILED,
                started_at=outcome.started_at,
                finished_at=self._safe_clock_not_before(outcome.finished_at),
                adapter_state=outcome.adapter_state,
                message=_error_message(error),
            )
        return outcome

    async def _persist_failure(
        self,
        job: ScheduledSourceJob,
        outcome: WorkerRunOutcome,
    ) -> WorkerRunOutcome:
        try:
            await self._store.persist_failure(job, outcome)
        except Exception as error:
            return WorkerRunOutcome(
                job_name=job.name,
                kind=job.kind,
                status=WorkerRunStatus.PERSISTENCE_FAILED,
                started_at=outcome.started_at,
                finished_at=self._safe_clock_not_before(outcome.finished_at),
                adapter_state=AdapterState.DOWN,
                message=_error_message(error),
            )
        return outcome

    @staticmethod
    def _validate_payload(job: ScheduledSourceJob, payload: AdapterPayload) -> None:
        if not isinstance(payload, AdapterPayload):
            raise TypeError("adapter must return AdapterPayload")
        expected_name = job.adapter.name.strip()
        if payload.name.strip() != expected_name:
            raise ValueError("adapter payload name mismatch")
        if payload.health.name.strip() != expected_name:
            raise ValueError("adapter health name mismatch")

    def _safe_clock_not_before(self, fallback: datetime) -> datetime:
        try:
            return self._clock_not_before(fallback)
        except Exception:
            return fallback

    def _clock_not_before(self, fallback: datetime) -> datetime:
        value = self._aware_clock()
        return value if value >= fallback else fallback

    def _aware_clock(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("runtime clock must return a timezone-aware datetime")
        return value
