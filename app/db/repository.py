from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DomainRecord


@dataclass(frozen=True)
class DomainRecordInput:
    record_type: str
    symbol: str
    state: str
    payload: dict[str, Any] = field(default_factory=dict)
    expires_at: datetime | None = None


class DomainRecordRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, item: DomainRecordInput) -> DomainRecord:
        record_type = item.record_type.strip()
        symbol = item.symbol.strip()
        state = item.state.strip()
        if not record_type or not symbol or not state:
            raise ValueError("record_type, symbol, and state are required")

        record = DomainRecord(
            record_type=record_type,
            symbol=symbol,
            state=state,
            payload=dict(item.payload),
            expires_at=item.expires_at,
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def list_by_type(
        self,
        record_type: str,
        *,
        limit: int = 100,
    ) -> list[DomainRecord]:
        normalized_type = record_type.strip()
        if not normalized_type:
            raise ValueError("record_type is required")
        if limit < 1 or limit > 500:
            raise ValueError("limit must be between 1 and 500")

        statement = (
            select(DomainRecord)
            .where(DomainRecord.record_type == normalized_type)
            .order_by(DomainRecord.created_at.desc())
            .limit(limit)
        )
        result = await self.session.scalars(statement)
        return list(result)
