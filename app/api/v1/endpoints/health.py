"""
Health check endpoint router.
Provides service liveness and diagnostic status for container orchestrators and monitoring tools.
"""

from fastapi import APIRouter, Depends
from app.schemas.health import HealthResponse
from app.core.config import Settings, get_settings

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Service Health Check",
    description="Returns the operational status, environment name, and version of the automation service."
)
async def get_health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    """
    Health check handler.
    Always returns HTTP 200 with service information when the process is operational.
    """
    return HealthResponse(
        status="ok",
        service="instagram-automation-service",
        environment=settings.ENVIRONMENT,
        version=settings.APP_VERSION
    )
