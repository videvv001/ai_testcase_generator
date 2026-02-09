from datetime import datetime, timezone

from fastapi import APIRouter

from app.core.config import get_settings


router = APIRouter()


@router.get("/health", summary="Service health check", tags=["health"])
async def health_check() -> dict:
    """
    Lightweight health check for readiness / liveness probes.
    """
    settings = get_settings()

    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.environment,
        "time": datetime.now(timezone.utc).isoformat(),
    }
