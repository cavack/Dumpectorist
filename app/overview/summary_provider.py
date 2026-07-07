from datetime import datetime
from typing import Protocol

from app.overview.models import OverviewSummary
from app.overview.provider import EmptyOverviewProvider
from app.overview.service import build_overview


class OverviewSummaryProvider(Protocol):
    async def summary(self, generated_at: datetime) -> OverviewSummary:
        """Return a read-only overview summary."""


class EmptySummaryProvider:
    def __init__(self) -> None:
        self.source = EmptyOverviewProvider()

    async def summary(self, generated_at: datetime) -> OverviewSummary:
        data = await self.source.load()
        return build_overview(data, generated_at)
