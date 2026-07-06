from datetime import datetime, timezone

from fastapi import APIRouter

from app.core.config import settings
from app.core.enums import HealthState

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    return {
        "status": HealthState.OK,
        "app": settings.app_name,
        "environment": settings.app_env,
        "live_actions_enabled": settings.enable_live_actions,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
