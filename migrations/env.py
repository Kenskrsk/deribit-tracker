import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.engine import Connection

from deribit_tracker.config import Settings
from deribit_tracker.db.engine import build_engine
from deribit_tracker.db.models import Base

if context.config.config_file_name is not None:
    fileConfig(context.config.config_file_name)


def run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    engine = build_engine(Settings().database_url, pooled=False)
    async with engine.connect() as connection:
        await connection.run_sync(run_migrations)
    await engine.dispose()


asyncio.run(run_async_migrations())
