from collections import Counter
from collections.abc import Iterable
from datetime import datetime
from enum import StrEnum

from app.flow.models import FlowStatus
from app.lifecycle.models import LifecycleState
from app.notifications.models import DeliveryStatus
from app.overview.data import OverviewData
from app.overview.models import OverviewSummary
from app.planning.models import PlanStatus
from app.setups.models import SetupLabel
from app.watchlist.models import WatchStage


def _require_aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("generated_at must be timezone-aware")


def _counts(enum_type: type[StrEnum], values: Iterable[StrEnum]) -> dict[str, int]:
    counter = Counter(value.value for value in values)
    return {member.value: counter.get(member.value, 0) for member in enum_type}


def build_overview(data: OverviewData, generated_at: datetime) -> OverviewSummary:
    _require_aware(generated_at)

    return OverviewSummary(
        generated_at=generated_at,
        mode=data.mode,
        totals={
            "watchlist": len(data.watchlist_entries),
            "setups": len(data.setup_candidates),
            "flow": len(data.flow_results),
            "plans": len(data.plan_drafts),
            "lifecycle": len(data.lifecycle_records),
            "deliveries": len(data.delivery_receipts),
        },
        watchlist=_counts(WatchStage, (item.stage for item in data.watchlist_entries)),
        setups=_counts(SetupLabel, (item.label for item in data.setup_candidates)),
        flow=_counts(FlowStatus, (item.status for item in data.flow_results)),
        plans=_counts(PlanStatus, (item.status for item in data.plan_drafts)),
        lifecycle=_counts(
            LifecycleState,
            (item.state for item in data.lifecycle_records),
        ),
        deliveries=_counts(
            DeliveryStatus,
            (item.status for item in data.delivery_receipts),
        ),
        notes=data.notes,
    )
