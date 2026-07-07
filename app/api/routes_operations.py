from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.config import settings
from app.ops.health import collect_default_health
from app.ops.models import OperationalHealth


router = APIRouter()


async def get_operational_health() -> OperationalHealth:
    return await collect_default_health(
        database_url=settings.database_url,
        redis_url=settings.redis_url,
        checked_at=datetime.now(timezone.utc),
    )


@router.get("/health/operations", response_model=OperationalHealth)
async def operational_health(
    status: Annotated[OperationalHealth, Depends(get_operational_health)],
) -> OperationalHealth:
    return status
