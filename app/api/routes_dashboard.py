from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends

from app.overview.models import OverviewSummary
from app.overview.runtime import get_overview_provider
from app.overview.summary_provider import OverviewSummaryProvider


router = APIRouter()


@router.get("/dashboard/summary", response_model=OverviewSummary)
async def dashboard_summary(
    provider: Annotated[OverviewSummaryProvider, Depends(get_overview_provider)],
) -> OverviewSummary:
    return await provider.summary(datetime.now(timezone.utc))
