from datetime import datetime, timezone

from fastapi import APIRouter

from app.overview.models import OverviewSummary
from app.overview.provider import EmptyOverviewProvider
from app.overview.service import build_overview


router = APIRouter()
provider = EmptyOverviewProvider()


@router.get("/dashboard/summary", response_model=OverviewSummary)
async def dashboard_summary() -> OverviewSummary:
    data = await provider.load()
    return build_overview(data, datetime.now(timezone.utc))
