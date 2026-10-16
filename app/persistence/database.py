"""Async SQLAlchemy database engine and session factory."""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings
from app.core.logging import logger


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""

    pass


# Global engine and sessionmaker
engine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def init_db() -> None:
    """Initializes tables asynchronously on startup."""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database tables: {e}")


async def close_db() -> None:
    """Closes database connection pool on shutdown."""
    await engine.dispose()
    logger.info("Database engine disposed.")


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for providing a scoped async session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
