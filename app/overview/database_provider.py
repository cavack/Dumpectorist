from datetime import datetime
from enum import StrEnum

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import DomainRecord
from app.flow.models import FlowStatus
from app.lifecycle.models import LifecycleState
from app.notifications.models import DeliveryStatus
from app.overview.models import OverviewMode, OverviewSummary
from app.planning.models import PlanStatus
from app.setups.models import SetupLabel
from app.watchlist.models import WatchStage


class OverviewRecordType(StrEnum):
    WATCHLIST = "watchlist"
    SETUP = "setup"
    FLOW = "flow"
    PLAN = "plan"
    LIFECYCLE = "lifecycle"
    DELIVERY = "delivery"


_RECORD_SECTIONS: dict[str, tuple[str, type[StrEnum]]] = {
    OverviewRecordType.WATCHLIST: ("watchlist", WatchStage),
    OverviewRecordType.SETUP: ("setups", SetupLabel),
    OverviewRecordType.FLOW: ("flow", FlowStatus),
    OverviewRecordType.PLAN: ("plans", PlanStatus),
    OverviewRecordType.LIFECYCLE: ("lifecycle", LifecycleState),
    OverviewRecordType.DELIVERY: ("deliveries", DeliveryStatus),
}


def _zero_counts(enum_type: type[StrEnum]) -> dict[str, int]:
    return {member.value: 0 for member in enum_type}


def _empty_sections() -> dict[str, dict[str, int]]:
    return {
        section: _zero_counts(enum_type)
        for section, enum_type in _RECORD_SECTIONS.values()
    }


def _summary(
    *,
    generated_at: datetime,
    mode: OverviewMode,
    sections: dict[str, dict[str, int]] | None = None,
    totals: dict[str, int] | None = None,
    notes: tuple[str, ...] = (),
) -> OverviewSummary:
    active_sections = sections or _empty_sections()
    active_totals = totals or {section: 0 for section in active_sections}
    return OverviewSummary(
        generated_at=generated_at,
        mode=mode,
        totals=active_totals,
        watchlist=active_sections["watchlist"],
        setups=active_sections["setups"],
        flow=active_sections["flow"],
        plans=active_sections["plans"],
        lifecycle=active_sections["lifecycle"],
        deliveries=active_sections["deliveries"],
        notes=notes,
    )


class DatabaseOverviewProvider:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def summary(self, generated_at: datetime) -> OverviewSummary:
        if generated_at.tzinfo is None or generated_at.utcoffset() is None:
            raise ValueError("generated_at must be timezone-aware")

        statement = (
            select(
                DomainRecord.record_type,
                DomainRecord.state,
                func.count(DomainRecord.id),
            )
            .group_by(DomainRecord.record_type, DomainRecord.state)
            .order_by(DomainRecord.record_type, DomainRecord.state)
        )

        try:
            async with self.session_factory() as session:
                rows = (await session.execute(statement)).all()
        except SQLAlchemyError as error:
            return _summary(
                generated_at=generated_at,
                mode=OverviewMode.DATABASE_UNAVAILABLE,
                notes=(f"Database overview unavailable: {type(error).__name__}",),
            )

        sections = _empty_sections()
        totals = {section: 0 for section in sections}
        ignored_records = 0
        unknown_states: dict[str, int] = {}

        for record_type, state, count_value in rows:
            count = int(count_value)
            mapping = _RECORD_SECTIONS.get(record_type)
            if mapping is None:
                ignored_records += count
                continue

            section, _ = mapping
            totals[section] += count
            if state in sections[section]:
                sections[section][state] += count
            else:
                sections[section]["UNKNOWN"] = sections[section].get("UNKNOWN", 0) + count
                unknown_states[section] = unknown_states.get(section, 0) + count

        notes: list[str] = []
        if not any(totals.values()):
            notes.append("No dashboard records are stored.")
        if ignored_records:
            notes.append(f"Ignored {ignored_records} non-dashboard records.")
        for section, count in sorted(unknown_states.items()):
            notes.append(f"{section} contains {count} records with unknown states.")

        return _summary(
            generated_at=generated_at,
            mode=OverviewMode.DATABASE,
            sections=sections,
            totals=totals,
            notes=tuple(notes),
        )
