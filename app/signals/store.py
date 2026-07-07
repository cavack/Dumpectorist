from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.repository import DomainRecordInput, DomainRecordRepository
from app.runtime.store import json_safe
from app.signals.models import SignalAssemblyReport


class SignalAssemblyStore(Protocol):
    async def persist(self, report: SignalAssemblyReport) -> None:
        """Persist one complete assembly report and lifecycle record."""


class InMemorySignalAssemblyStore:
    def __init__(self) -> None:
        self.reports: list[SignalAssemblyReport] = []

    async def persist(self, report: SignalAssemblyReport) -> None:
        self.reports.append(report)


class DomainRecordSignalAssemblyStore:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self.session_factory = session_factory

    async def persist(self, report: SignalAssemblyReport) -> None:
        assembly_payload = json_safe(report)
        lifecycle_payload = json_safe(
            {
                "symbol": report.symbol,
                "assembly_status": report.status,
                "setup_type": report.setup_type,
                "assembled_at": report.assembled_at,
                "lifecycle": report.lifecycle,
                "reasons": report.reasons,
                "gates": report.gates,
            }
        )

        async with self.session_factory() as session:
            repository = DomainRecordRepository(session)
            await repository.add(
                DomainRecordInput(
                    record_type="signal_assembly",
                    symbol=report.symbol,
                    state=report.status.value,
                    payload=assembly_payload,
                    expires_at=report.lifecycle.expires_at,
                )
            )
            await repository.add(
                DomainRecordInput(
                    record_type="signal_lifecycle",
                    symbol=report.symbol,
                    state=report.lifecycle.state.value,
                    payload=lifecycle_payload,
                    expires_at=report.lifecycle.expires_at,
                )
            )
            await session.commit()
