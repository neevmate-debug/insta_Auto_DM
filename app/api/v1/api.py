"""
API v1 Router Aggregator.
Combines all v1 endpoint routers under the /api/v1 prefix.
"""

from fastapi import APIRouter
from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.webhooks import router as webhooks_router

api_v1_router = APIRouter()

# Register endpoint routers
api_v1_router.include_router(health_router, tags=["Health"])
api_v1_router.include_router(webhooks_router, tags=["Meta Webhooks"])
