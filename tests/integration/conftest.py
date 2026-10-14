import os
from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from deribit_tracker.db.engine import build_engine, build_session_factory
from deribit_tracker.db.models import Base

pytestmark = pytest.mark.integration


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    """Session on a freshly created schema; skipped when no test database is configured."""
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is not set (run `make test`)")

    engine = build_engine(database_url, pooled=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)

    async with build_session_factory(engine)() as session:
        yield session
    await engine.dispose()
