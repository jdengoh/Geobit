import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

# TODO: Set dynamic echo based on environment

engine = create_async_engine(
    str(settings.SQLALCHEMY_DATABASE_URI),
    echo=False,  # Set to True for debugging, False in production
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)

logger.info(f"Database engine created with URL: {engine.url}")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for async database sessions"""
    async with AsyncSessionLocal() as session:
        try:
            async with session.begin():
                yield session
        except Exception as e:
            logger.error(f"Database session error: {e}")
            await session.rollback()
            raise
