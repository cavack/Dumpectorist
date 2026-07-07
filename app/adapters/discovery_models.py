from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any


class DiscoverySource(StrEnum):
    DEX_SCREENER = "DEX_SCREENER"
    COINGECKO = "COINGECKO"


class DiscoveryRole(StrEnum):
    DISCOVERY_ONLY = "DISCOVERY_ONLY"


@dataclass(frozen=True)
class DiscoveryRecord:
    source: DiscoverySource
    role: DiscoveryRole
    external_id: str
    symbol: str | None = None
    name: str | None = None
    chain_id: str | None = None
    token_address: str | None = None
    category: str | None = None
    price_usd: Decimal | None = None
    liquidity_usd: Decimal | None = None
    volume_24h_usd: Decimal | None = None
    market_cap_usd: Decimal | None = None
    price_change_24h_pct: Decimal | None = None
    boost_active: int | None = None
    pair_created_at: datetime | None = None
    url: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.role != DiscoveryRole.DISCOVERY_ONLY:
            raise ValueError("discovery role must remain DISCOVERY_ONLY")
        if not self.external_id.strip():
            raise ValueError("external_id is required")
        for value, name in (
            (self.price_usd, "price_usd"),
            (self.liquidity_usd, "liquidity_usd"),
            (self.volume_24h_usd, "volume_24h_usd"),
            (self.market_cap_usd, "market_cap_usd"),
        ):
            if value is not None and value < 0:
                raise ValueError(f"{name} must be non-negative")
        if self.boost_active is not None and self.boost_active < 0:
            raise ValueError("boost_active must be non-negative")
        if self.pair_created_at is not None and (
            self.pair_created_at.tzinfo is None
            or self.pair_created_at.utcoffset() is None
        ):
            raise ValueError("pair_created_at must be timezone-aware")


@dataclass(frozen=True)
class DiscoveryBatch:
    source: DiscoverySource
    role: DiscoveryRole
    query: str
    fetched_at: datetime
    records: tuple[DiscoveryRecord, ...]
    cache_hit: bool = False

    def __post_init__(self) -> None:
        if self.role != DiscoveryRole.DISCOVERY_ONLY:
            raise ValueError("discovery batch role must remain DISCOVERY_ONLY")
        if not self.query.strip():
            raise ValueError("query is required")
        if self.fetched_at.tzinfo is None or self.fetched_at.utcoffset() is None:
            raise ValueError("fetched_at must be timezone-aware")
        if any(record.source != self.source for record in self.records):
            raise ValueError("all records must match batch source")
