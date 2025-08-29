# app/database/db.py

import logging
from typing import AsyncGenerator, Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_client: Optional[AsyncIOMotorClient] = None
_db: Optional[AsyncIOMotorDatabase] = None

def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        logger.info("Creating MongoDB client…")
        _client = AsyncIOMotorClient(str(settings.MONGODB_URI), uuidRepresentation="standard")
        logger.info("MongoDB client created")
    return _client

def get_database() -> AsyncIOMotorDatabase:
    client = get_client()
    return client[str(settings.MONGODB_DB_NAME)]

# ✅ SYNC getter for repositories/services (returns the db object)
def get_db() -> AsyncIOMotorDatabase:
    return get_database()

# ✅ ASYNC dependency for FastAPI routes (use with Depends)
async def get_db_dep() -> AsyncGenerator[AsyncIOMotorDatabase, None]:
    db = get_database()
    try:
        await db.command("ping")  # fail fast if connection is bad
        yield db
    except Exception as e:
        logger.error(f"MongoDB dependency error: {e}")
        raise

async def close_db_client() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None
        logger.info("MongoDB client closed")