from typing import Annotated

from fastapi import APIRouter, Query

from deribit_tracker.api.dependencies import PriceServiceDep
from deribit_tracker.api.schemas import ErrorResponse, PriceResponse
from deribit_tracker.domain import PriceSnapshot, Ticker

# Values above this do not fit PostgreSQL BIGINT and would fail inside the query.
MAX_BIGINT = 2**63 - 1

TickerQuery = Annotated[Ticker, Query(description="Currency pair, e.g. btc_usd")]
LimitQuery = Annotated[
    int | None, Query(ge=1, le=10_000, description="Max records to return; omit to get all")
]
OffsetQuery = Annotated[int, Query(ge=0, le=MAX_BIGINT, description="Records to skip")]
DateFromQuery = Annotated[
    int | None, Query(ge=0, le=MAX_BIGINT, description="Range start, UNIX seconds, inclusive")
]
DateToQuery = Annotated[
    int | None, Query(ge=0, le=MAX_BIGINT, description="Range end, UNIX seconds, inclusive")
]


async def get_prices(
    ticker: TickerQuery,
    service: PriceServiceDep,
    limit: LimitQuery = None,
    offset: OffsetQuery = 0,
) -> list[PriceSnapshot]:
    """Prices in chronological order. Pagination is optional."""
    return await service.get_history(ticker, limit=limit, offset=offset)


async def get_latest_price(ticker: TickerQuery, service: PriceServiceDep) -> PriceSnapshot:
    return await service.get_latest(ticker)


async def get_prices_by_date(
    ticker: TickerQuery,
    service: PriceServiceDep,
    date_from: DateFromQuery = None,
    date_to: DateToQuery = None,
    limit: LimitQuery = None,
    offset: OffsetQuery = 0,
) -> list[PriceSnapshot]:
    """Prices with `date_from <= timestamp <= date_to`. Either bound may be omitted."""
    return await service.get_by_date_range(
        ticker, date_from=date_from, date_to=date_to, limit=limit, offset=offset
    )


def create_prices_router() -> APIRouter:
    """All price endpoints are GET and require `ticker`."""
    router = APIRouter(prefix="/prices", tags=["prices"])
    router.add_api_route(
        "",
        get_prices,
        summary="All stored prices of a ticker",
        response_model=list[PriceResponse],
    )
    router.add_api_route(
        "/latest",
        get_latest_price,
        summary="Latest price of a ticker",
        response_model=PriceResponse,
        responses={404: {"model": ErrorResponse, "description": "No prices stored yet"}},
    )
    router.add_api_route(
        "/by-date",
        get_prices_by_date,
        summary="Prices of a ticker within a date range",
        response_model=list[PriceResponse],
    )
    return router
