from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool


def build_engine(database_url: str, *, pooled: bool = True) -> AsyncEngine:
    """Create an async engine.

    `pooled=False` is used by Celery tasks: each task runs in a fresh event loop
    (`asyncio.run`), and pooled asyncpg connections cannot be reused across loops.
    """
    if pooled:
        return create_async_engine(database_url, pool_pre_ping=True)
    return create_async_engine(database_url, poolclass=NullPool)


def build_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
