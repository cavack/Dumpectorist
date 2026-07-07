from datetime import datetime, timedelta, timezone

import pytest

from app.flow.models import FlowResult, FlowStatus
from app.lifecycle.models import LifecycleRecord, LifecycleState
from app.notifications.models import (
    DeliveryReceipt,
    DeliveryStatus,
    NotificationChannel,
)
from app.overview.data import OverviewData
from app.overview.models import OverviewMode
from app.overview.service import build_overview
from app.planning.models import PlanDraft, PlanStatus
from app.setups.models import SetupCandidate, SetupLabel
from app.watchlist.models import WatchStage, WatchlistEntry


NOW = datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)


def test_overview_counts_domain_records_by_status():
    data = OverviewData(
        watchlist_entries=(
            WatchlistEntry(
                symbol="A",
                stage=WatchStage.WATCHING,
                source="unit",
                data={"symbol": "A", "price": "1"},
            ),
            WatchlistEntry(
                symbol="B",
                stage=WatchStage.PAUSED,
                source="unit",
                data={"symbol": "B", "price": "2"},
            ),
        ),
        setup_candidates=(
            SetupCandidate(
                symbol="A",
                label=SetupLabel.REVIEW,
                source_state="ALERT",
                data={},
            ),
        ),
        flow_results=(
            FlowResult(symbol="A", status=FlowStatus.READY),
        ),
        plan_drafts=(
            PlanDraft(symbol="A", status=PlanStatus.READY),
        ),
        lifecycle_records=(
            LifecycleRecord(
                symbol="A",
                state=LifecycleState.ACTIVE,
                created_at=NOW,
                updated_at=NOW,
                expires_at=NOW + timedelta(minutes=30),
            ),
        ),
        delivery_receipts=(
            DeliveryReceipt(
                symbol="A",
                channel=NotificationChannel.TELEGRAM,
                status=DeliveryStatus.SKIPPED,
            ),
        ),
        mode=OverviewMode.IN_MEMORY,
    )

    summary = build_overview(data, NOW)

    assert summary.totals == {
        "watchlist": 2,
        "setups": 1,
        "flow": 1,
        "plans": 1,
        "lifecycle": 1,
        "deliveries": 1,
    }
    assert summary.watchlist["WATCHING"] == 1
    assert summary.watchlist["PAUSED"] == 1
    assert summary.watchlist["NEW"] == 0
    assert summary.setups["REVIEW"] == 1
    assert summary.flow["READY"] == 1
    assert summary.plans["READY"] == 1
    assert summary.lifecycle["ACTIVE"] == 1
    assert summary.deliveries["SKIPPED"] == 1


def test_overview_requires_timezone_aware_timestamp():
    with pytest.raises(ValueError):
        build_overview(OverviewData(), datetime(2026, 7, 7, 12, 0))
