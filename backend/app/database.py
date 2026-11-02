"""SQLAlchemy async database engine, session factory, and base model.

Provides the core database infrastructure using SQLAlchemy 2.0 async APIs.
"""

from collections.abc import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()


def enable_sqlite_foreign_keys(async_engine: AsyncEngine) -> None:
    """Turn on FOREIGN KEY enforcement for SQLite connections.

    SQLite ignores ``ON DELETE CASCADE`` unless ``PRAGMA foreign_keys=ON`` is
    set on every connection. PostgreSQL always enforces it, so this is a no-op there.
    """
    if async_engine.dialect.name != "sqlite":
        return

    @event.listens_for(async_engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
    pool_pre_ping=True,
)
enable_sqlite_foreign_keys(engine)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """SQLAlchemy declarative base class for all ORM models.

    All database models should inherit from this base to be
    included in Alembic migrations and table creation.
    """

    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Provide an async database session as a FastAPI dependency.

    Yields an ``AsyncSession`` and ensures it is closed after use,
    even if an exception occurs.

    Yields:
        AsyncSession: An active async database session.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Create all database tables from ORM metadata.

    .. warning::
        This is intended for development and testing only.
        Use Alembic migrations for production deployments.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
