from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from app.adapters.benchmark_models import BenchmarkSnapshot
from app.adapters.discovery_models import DiscoveryRecord
from app.adapters.lbank_models import LBankExecutionSnapshot
from app.execution.consensus import ConsensusRules, CrossExchangeConsensusReport
from app.execution.lbank_validator import LBankExecutionValidation
from app.execution.symbol_mapping import CrossExchangeSymbolMap
from app.flow.models import FlowResult
from app.lifecycle.models import LifecycleRecord
from app.planning.models import PlanDraft, PlanRequest
from app.setups.models import SetupCandidate
from app.structure.models import StructureInput, StructureSnapshot


class ShortSetupType(StrEnum):
    BREAKDOWN_SHORT = "BREAKDOWN_SHORT"
    FAILED_PULLBACK_SHORT = "FAILED_PULLBACK_SHORT"
    CONTINUATION_SHORT = "CONTINUATION_SHORT"


class SignalAssemblyStatus(StrEnum):
    HYPE_WATCH = "HYPE_WATCH"
    WEAKNESS_WATCH = "WEAKNESS_WATCH"
    BREAKDOWN_WATCH = "BREAKDOWN_WATCH"
    EXECUTION_PENDING = "EXECUTION_PENDING"
    DATA_DEGRADED = "DATA_DEGRADED"
    AVOID = "AVOID"
    SHORT_READY = "SHORT_READY"


class GateState(StrEnum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    SKIP = "SKIP"


class HigherTimeframeEvidenceOrigin(StrEnum):
    MANUAL = "MANUAL"
    DERIVED = "DERIVED"


@dataclass(frozen=True)
class GateDecision:
    name: str
    state: GateState
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("gate name is required")

    @property
    def passed(self) -> bool:
        return self.state in {GateState.PASS, GateState.WARN}


@dataclass(frozen=True)
class HigherTimeframeStructureEvidence:
    symbol: str
    observed_at: datetime
    daily_damaged: bool
    four_hour_damaged: bool
    origin: HigherTimeframeEvidenceOrigin = HigherTimeframeEvidenceOrigin.MANUAL
    market_symbol: str | None = None
    daily_zone_id: str | None = None
    daily_event_id: str | None = None
    four_hour_zone_id: str | None = None
    four_hour_event_id: str | None = None
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        symbol = self.symbol.strip()
        if not symbol:
            raise ValueError("higher-timeframe symbol is required")
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("higher-timeframe observed_at must be timezone-aware")
        market_symbol = (
            None if self.market_symbol is None else self.market_symbol.strip().upper()
        )
        if self.origin == HigherTimeframeEvidenceOrigin.DERIVED:
            if not market_symbol:
                raise ValueError("derived evidence requires market_symbol")
            if self.daily_damaged and not (
                self.daily_zone_id and self.daily_event_id
            ):
                raise ValueError("damaged Daily evidence requires zone and event IDs")
            if self.four_hour_damaged and not (
                self.four_hour_zone_id and self.four_hour_event_id
            ):
                raise ValueError("damaged 4H evidence requires zone and event IDs")
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "market_symbol", market_symbol)


@dataclass(frozen=True)
class SignalAssemblyRules:
    max_structure_age_minutes: float = 360.0
    max_entry_deviation_bps: Decimal = Decimal("50")
    lifecycle_ttl_minutes: int = 60
    max_discovery_records: int = 50
    consensus: ConsensusRules = field(default_factory=ConsensusRules)

    def __post_init__(self) -> None:
        if self.max_structure_age_minutes <= 0:
            raise ValueError("max_structure_age_minutes must be positive")
        if self.max_entry_deviation_bps <= 0:
            raise ValueError("max_entry_deviation_bps must be positive")
        if self.lifecycle_ttl_minutes <= 0:
            raise ValueError("lifecycle_ttl_minutes must be positive")
        if self.max_discovery_records < 0 or self.max_discovery_records > 500:
            raise ValueError("max_discovery_records must be between 0 and 500")


@dataclass(frozen=True)
class SignalAssemblyRequest:
    symbol: str
    setup_type: ShortSetupType
    higher_timeframe: HigherTimeframeStructureEvidence
    structure_input: StructureInput
    lbank_snapshot: LBankExecutionSnapshot
    benchmark_snapshots: tuple[BenchmarkSnapshot, ...]
    symbol_map: CrossExchangeSymbolMap
    plan_request: PlanRequest
    discovery_records: tuple[DiscoveryRecord, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        normalized_symbol = self.symbol.strip()
        if not normalized_symbol:
            raise ValueError("assembly symbol is required")
        object.__setattr__(self, "symbol", normalized_symbol)


@dataclass(frozen=True)
class SignalAssemblyReport:
    symbol: str
    setup_type: ShortSetupType
    status: SignalAssemblyStatus
    assembled_at: datetime
    discovery_records: tuple[DiscoveryRecord, ...]
    higher_timeframe: HigherTimeframeStructureEvidence
    gates: tuple[GateDecision, ...]
    reasons: tuple[str, ...]
    plan: PlanDraft
    lifecycle: LifecycleRecord
    structure: StructureSnapshot | None = None
    setup: SetupCandidate | None = None
    flow: FlowResult | None = None
    lbank_validation: LBankExecutionValidation | None = None
    consensus: CrossExchangeConsensusReport | None = None
    entry_deviation_bps: Decimal | None = None

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("report symbol is required")
        if self.assembled_at.tzinfo is None or self.assembled_at.utcoffset() is None:
            raise ValueError("assembled_at must be timezone-aware")

    @property
    def is_short_ready(self) -> bool:
        return self.status == SignalAssemblyStatus.SHORT_READY
