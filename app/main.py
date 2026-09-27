"""
Main entry point for the Instagram & Facebook Automation FastAPI application.

Provides:
- Application initialization with metadata and lifespan events
- Direct /health endpoint for orchestration checks
- /api/v1 router mounting for modular endpoints
- OpenAPI / Swagger documentation at /docs
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings
from app.schemas.health import HealthResponse
from app.api.v1.api import api_v1_router

# Setup logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager.
    Handles startup and shutdown events cleanly.
    """
    settings = get_settings()
    logger.info("Starting %s (v%s) in [%s] mode...", settings.APP_NAME, settings.APP_VERSION, settings.ENVIRONMENT)

    # Informational notice regarding integration state
    if not settings.META_PAGE_ACCESS_TOKEN or not settings.META_APP_SECRET:
        logger.info(
            "Meta credentials are not configured. Running in scaffolding/testing mode without live Meta integration."
        )
    else:
        logger.info("Meta credentials detected.")

    yield

    logger.info("Shutting down %s...", settings.APP_NAME)


def create_application() -> FastAPI:
    """
    Application factory.
    Configures settings, middlewares, and routes.
    """
    settings = get_settings()

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "Backend automation service for Instagram and Facebook. "
            "Listens for comment webhooks and sends automated direct replies via official Meta APIs."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan
    )

    # Enable CORS for local testing and frontend tooling
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Top-level Health Check endpoint (/health) as requested
    @app.get(
        "/health",
        response_model=HealthResponse,
        tags=["Health"],
        summary="Root Health Check",
        description="Root liveness check returning basic service information."
    )
    async def root_health():
        return HealthResponse(
            status="ok",
            service="instagram-automation-service",
            environment=settings.ENVIRONMENT,
            version=settings.APP_VERSION
        )

    # Root informational route
    @app.get("/", tags=["Info"], summary="Service Information")
    async def root_info():
        return {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "status": "online",
            "documentation": "/docs",
            "health_check": "/health"
        }

    # Mount API v1 router (includes /api/v1/health and /api/v1/webhooks)
    app.include_router(api_v1_router, prefix="/api/v1")

    return app


app = create_application()


if __name__ == "__main__":
    import uvicorn
    app_settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=app_settings.HOST,
        port=app_settings.PORT,
        reload=app_settings.DEBUG
    )
