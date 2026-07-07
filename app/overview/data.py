from dataclasses import dataclass, field

from app.flow.models import FlowResult
from app.lifecycle.models import LifecycleRecord
from app.notifications.models import DeliveryReceipt
from app.overview.models import OverviewMode
from app.planning.models import PlanDraft
from app.setups.models import SetupCandidate
from app.watchlist.models import WatchlistEntry


@dataclass(frozen=True)
class OverviewData:
    watchlist_entries: tuple[WatchlistEntry, ...] = ()
    setup_candidates: tuple[SetupCandidate, ...] = ()
    flow_results: tuple[FlowResult, ...] = ()
    plan_drafts: tuple[PlanDraft, ...] = ()
    lifecycle_records: tuple[LifecycleRecord, ...] = ()
    delivery_receipts: tuple[DeliveryReceipt, ...] = ()
    mode: OverviewMode = OverviewMode.IN_MEMORY
    notes: tuple[str, ...] = field(default_factory=tuple)
