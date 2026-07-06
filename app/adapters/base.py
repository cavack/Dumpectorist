from typing import Protocol

from app.adapters.models import AdapterHealth, AdapterPayload


class Adapter(Protocol):
    name: str

    async def health(self) -> AdapterHealth:
        """Return current adapter health."""

    async def load(self) -> AdapterPayload:
        """Load and parse one payload."""
