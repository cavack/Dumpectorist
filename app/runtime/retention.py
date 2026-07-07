from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import DomainRecord


RUNTIME_RECORD_TYPES = (
    "execution_snapshot",
    "benchmark_snapshot",
    "discovery_snapshot",
    "source_diagnostic",
    "source_health",
    "worker_run",
    "worker_metrics",
)


@dataclass(frozen=True)
class RetentionPolicy:
    retention_days: int
    record_types: tuple[str, ...] = RUNTIME_RECORD_TYPES

    def __post_init__(self) -> None:
        if self.retention_days < 1:
            raise ValueError("retention_days must be positive")
        normalized = tuple(dict.fromkeys(item.strip() for item in self.record_types if item.strip()))
        if not normalized:
            raise ValueError("record_types must not be empty")
        object.__setattr__(self, "record_types", normalized)


@dataclass(frozen=True)
class RetentionResult:
    cutoff: datetime
    deleted_records: int

    def __post_init__(self) -> None:
        if self.cutoff.tzinfo is None or self.cutoff.utcoffset() is None:
            raise ValueError("cutoff must be timezone-aware")
        if self.deleted_records < 0:
            raise ValueError("deleted_records must be non-negative")


class DomainRecordRetentionCleaner:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        policy: RetentionPolicy,
    ) -> None:
        self.session_factory = session_factory
        self.policy = policy

    async def cleanup(self, *, now: datetime) -> RetentionResult:
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("now must be timezone-aware")
        cutoff = now - timedelta(days=self.policy.retention_days)

        async with self.session_factory() as session:
            result = await session.execute(
                delete(DomainRecord).where(
                    DomainRecord.record_type.in_(self.policy.record_types),
                    DomainRecord.created_at < cutoff,
                )
            )
            await session.commit()

        return RetentionResult(
            cutoff=cutoff,
            deleted_records=max(result.rowcount or 0, 0),
        )
