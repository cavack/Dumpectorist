from typing import Protocol

from app.overview.data import OverviewData
from app.overview.models import OverviewMode


class OverviewProvider(Protocol):
    async def load(self) -> OverviewData:
        """Load the current read-only overview data."""


class EmptyOverviewProvider:
    async def load(self) -> OverviewData:
        return OverviewData(
            mode=OverviewMode.NO_STORE,
            notes=("No persistence provider is configured.",),
        )
