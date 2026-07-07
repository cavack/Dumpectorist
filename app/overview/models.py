from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class OverviewMode(StrEnum):
    NO_STORE = "NO_STORE"
    IN_MEMORY = "IN_MEMORY"


class OverviewSummary(BaseModel):
    generated_at: datetime
    mode: OverviewMode
    totals: dict[str, int] = Field(default_factory=dict)
    watchlist: dict[str, int] = Field(default_factory=dict)
    setups: dict[str, int] = Field(default_factory=dict)
    flow: dict[str, int] = Field(default_factory=dict)
    plans: dict[str, int] = Field(default_factory=dict)
    lifecycle: dict[str, int] = Field(default_factory=dict)
    deliveries: dict[str, int] = Field(default_factory=dict)
    notes: tuple[str, ...] = ()
