"""
Pydantic schema definitions for system health checks.
"""

from datetime import datetime, timezone
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """
    Standard health check response model.
    """
    status: str = Field(..., examples=["ok"], description="Status of the API service")
    service: str = Field(..., examples=["instagram-automation-service"], description="Service identifier")
    environment: str = Field(..., examples=["development"], description="Current operating environment")
    version: str = Field(..., examples=["0.1.0"], description="Semantic version of the service")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of the health check"
    )
