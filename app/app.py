import logging

from fastapi import APIRouter, FastAPI
from fastapi.concurrency import asynccontextmanager
from fastapi.params import Depends

from app.api import agent, jargon
from app.config import CONFIG_AGENT_SERVICE
from app.core.config import Settings, get_settings
from app.services.agent_service import AgentService
from app.database.db import close_db_client


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

    setattr(app.state, CONFIG_AGENT_SERVICE, AgentService())

    # TODO: Any client initialization can be done here
    # s = get_settings()

    logger.info("Application started")
    yield

    logger.info("Application stopped")


def create_app() -> FastAPI:
    app = FastAPI(title="geobit", lifespan=lifespan)

    # Setup routers
    routers = [router, agent.router, jargon.router]
    for r in routers:
        app.include_router(r)

    
    @app.on_event("shutdown")
    async def _shutdown():
        await close_db_client()
    return app

