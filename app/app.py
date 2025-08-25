import logging

from fastapi import APIRouter, FastAPI
from fastapi.concurrency import asynccontextmanager
from fastapi.params import Depends

from app.api import (
    login,
)
from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)
router = APIRouter()


# @router.get("/health", summary="Health Check")
# async def health_check():
#     """Health check endpoint to verify if the application is running."""
#     return {"status": "ok", "message": "Application is running"}


@router.get("/config", summary="Configuration")
async def get_config(s: Settings = Depends(get_settings)):
    """Get application configuration."""
    return s.__dict__


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan event handler."""
    logger.info("Starting application...")

    # TODO: Any client initialization can be done here
    # s = get_settings()

    logger.info("Application started")
    yield

    logger.info("Application stopped")


def create_app() -> FastAPI:
    app = FastAPI(title="geobit", lifespan=lifespan)

    # Setup routers
    routers = [router, login.router]
    for r in routers:
        app.include_router(r)

    return app
