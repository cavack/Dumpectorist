from dataclasses import asdict, is_dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters.models import AdapterPayload, AdapterState
from app.db.repository import DomainRecordInput, DomainRecordRepository
from app.runtime.models import ScheduledSourceJob, WorkerRunOutcome


class RuntimeStore(Protocol):
    async def persist_payload(
        self,
        job: ScheduledSourceJob,
        payload: AdapterPayload,
        outcome: WorkerRunOutcome,
    ) -> None:
        """Persist one source payload, source health record, and worker run."""

    async def persist_failure(
        self,
        job: ScheduledSourceJob,
        outcome: WorkerRunOutcome,
    ) -> None:
        """Persist a failed worker run and down source-health record."""


def json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, Enum):
        return json_safe(value.value)
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("persisted datetime must be timezone-aware")
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if is_dataclass(value):
        return json_safe(asdict(value))
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, (set, frozenset)):
        normalized = [json_safe(item) for item in value]
        return sorted(normalized, key=repr)
    raise TypeError(f"unsupported persistence value: {type(value).__name__}")


def _record_symbol(job: ScheduledSourceJob, payload: AdapterPayload | None = None) -> str:
    if payload is not None:
        for field in ("symbol", "query"):
            raw = payload.data.get(field)
            if isinstance(raw, str) and raw.strip():
                return raw.strip()
    return job.name


class NullRuntimeStore:
    async def persist_payload(
        self,
        job: ScheduledSourceJob,
        payload: AdapterPayload,
        outcome: WorkerRunOutcome,
    ) -> None:
        return None

    async def persist_failure(
        self,
        job: ScheduledSourceJob,
        outcome: WorkerRunOutcome,
    ) -> None:
        return None


class InMemoryRuntimeStore:
    def __init__(self) -> None:
        self.payload_runs: list[
            tuple[ScheduledSourceJob, AdapterPayload, WorkerRunOutcome]
        ] = []
        self.failure_runs: list[tuple[ScheduledSourceJob, WorkerRunOutcome]] = []

    async def persist_payload(
        self,
        job: ScheduledSourceJob,
        payload: AdapterPayload,
        outcome: WorkerRunOutcome,
    ) -> None:
        self.payload_runs.append((job, payload, outcome))

    async def persist_failure(
        self,
        job: ScheduledSourceJob,
        outcome: WorkerRunOutcome,
    ) -> None:
        self.failure_runs.append((job, outcome))


class DomainRecordRuntimeStore:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self.session_factory = session_factory

    async def persist_payload(
        self,
        job: ScheduledSourceJob,
        payload: AdapterPayload,
        outcome: WorkerRunOutcome,
    ) -> None:
        symbol = _record_symbol(job, payload)
        snapshot_type = f"{job.kind.value.lower()}_snapshot"
        snapshot_payload = {
            "job_name": job.name,
            "adapter_name": payload.name,
            "kind": job.kind.value,
            "data": payload.data,
        }
        health_payload = {
            "job_name": job.name,
            "adapter_name": payload.health.name,
            "kind": job.kind.value,
            "latency_ms": payload.health.latency_ms,
            "message": payload.health.message,
            "observed_at": outcome.finished_at,
        }
        run_payload = {
            "job_name": job.name,
            "adapter_name": payload.name,
            "kind": job.kind.value,
            "started_at": outcome.started_at,
            "finished_at": outcome.finished_at,
            "duration_ms": outcome.duration_ms,
            "adapter_state": payload.health.state.value,
            "message": outcome.message,
        }

        async with self.session_factory() as session:
            repository = DomainRecordRepository(session)
            await repository.add(
                DomainRecordInput(
                    record_type=snapshot_type,
                    symbol=symbol,
                    state=payload.health.state.value,
                    payload=json_safe(snapshot_payload),
                )
            )
            await repository.add(
                DomainRecordInput(
                    record_type="source_health",
                    symbol=symbol,
                    state=payload.health.state.value,
                    payload=json_safe(health_payload),
                )
            )
            await repository.add(
                DomainRecordInput(
                    record_type="worker_run",
                    symbol=symbol,
                    state=outcome.status.value,
                    payload=json_safe(run_payload),
                )
            )
            await session.commit()

    async def persist_failure(
        self,
        job: ScheduledSourceJob,
        outcome: WorkerRunOutcome,
    ) -> None:
        symbol = _record_symbol(job)
        health_payload = {
            "job_name": job.name,
            "adapter_name": job.adapter.name,
            "kind": job.kind.value,
            "message": outcome.message,
            "observed_at": outcome.finished_at,
        }
        run_payload = {
            "job_name": job.name,
            "adapter_name": job.adapter.name,
            "kind": job.kind.value,
            "started_at": outcome.started_at,
            "finished_at": outcome.finished_at,
            "duration_ms": outcome.duration_ms,
            "adapter_state": AdapterState.DOWN.value,
            "message": outcome.message,
        }

        async with self.session_factory() as session:
            repository = DomainRecordRepository(session)
            await repository.add(
                DomainRecordInput(
                    record_type="source_health",
                    symbol=symbol,
                    state=AdapterState.DOWN.value,
                    payload=json_safe(health_payload),
                )
            )
            await repository.add(
                DomainRecordInput(
                    record_type="worker_run",
                    symbol=symbol,
                    state=outcome.status.value,
                    payload=json_safe(run_payload),
                )
            )
            await session.commit()
