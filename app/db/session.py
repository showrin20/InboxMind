"""
Database session management with async support
"""
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker
)
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool, AsyncAdaptedQueuePool
import logging

from app.core.config import get_settings
from app.db.base import Base

settings = get_settings()
logger = logging.getLogger(__name__)


# Async engine configuration
_is_sqlite = settings.DATABASE_URL.startswith("sqlite")

if _is_sqlite:
    engine = create_async_engine(
        settings.get_database_url(async_driver=True),
        echo=settings.DB_ECHO,
        poolclass=NullPool,
        future=True,
    )
else:
    engine = create_async_engine(
        settings.get_database_url(async_driver=True),
        echo=settings.DB_ECHO,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        poolclass=AsyncAdaptedQueuePool,
        future=True,
    )

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for FastAPI routes to get async database session.
    
    Usage:
        @router.get("/endpoint")
        async def endpoint(db: AsyncSession = Depends(get_async_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """
    Initialize database - create all tables.
    Should be called on application startup.
    """
    try:
        async with engine.begin() as conn:
            # Import all models to ensure they're registered
            from app.models.user import User
            from app.models.email import Email
            from app.models.vector_record import VectorRecord
            from app.models.rag_query import RAGQuery
            from app.models.audit_log import AuditLog
            
            # Create all tables
            await conn.run_sync(Base.metadata.create_all)
            
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


async def close_db() -> None:
    """
    Close database connections.
    Should be called on application shutdown.
    """
    await engine.dispose()
    logger.info("Database connections closed")


# Export for convenience
__all__ = ["get_async_db", "init_db", "close_db", "AsyncSessionLocal", "engine"]
