from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from deribit_tracker.repositories.prices import PriceRepository
from deribit_tracker.services.prices import PriceQueryService


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.session_factory() as session:
        yield session


def get_price_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PriceQueryService:
    return PriceQueryService(PriceRepository(session))


PriceServiceDep = Annotated[PriceQueryService, Depends(get_price_service)]
