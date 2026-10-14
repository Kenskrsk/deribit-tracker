from typing import Annotated

from fastapi import APIRouter, Query

from deribit_tracker.api.dependencies import PriceServiceDep
from deribit_tracker.api.schemas import ErrorResponse, PriceResponse
from deribit_tracker.domain import Ticker

TickerQuery = Annotated[Ticker, Query(description="Currency pair, e.g. btc_usd")]
LimitQuery = Annotated[
    int | None, Query(ge=1, le=10_000, description="Max records to return; omit to get all")
]
OffsetQuery = Annotated[int, Query(ge=0, description="Records to skip")]
DateFromQuery = Annotated[
    int | None, Query(ge=0, description="Range start, UNIX seconds, inclusive")
]
DateToQuery = Annotated[int | None, Query(ge=0, description="Range end, UNIX seconds, inclusive")]

router = APIRouter(prefix="/prices", tags=["prices"])


@router.get("", summary="All stored prices of a ticker", response_model=list[PriceResponse])
async def get_prices(
    ticker: TickerQuery,
    service: PriceServiceDep,
    limit: LimitQuery = None,
    offset: OffsetQuery = 0,
) -> list[PriceResponse]:
    """Prices in chronological order. Pagination is optional."""
    snapshots = await service.get_history(ticker, limit=limit, offset=offset)
    return [PriceResponse.model_validate(snapshot) for snapshot in snapshots]


@router.get(
    "/latest",
    summary="Latest price of a ticker",
    response_model=PriceResponse,
    responses={404: {"model": ErrorResponse, "description": "No prices stored yet"}},
)
async def get_latest_price(ticker: TickerQuery, service: PriceServiceDep) -> PriceResponse:
    snapshot = await service.get_latest(ticker)
    return PriceResponse.model_validate(snapshot)


@router.get(
    "/by-date",
    summary="Prices of a ticker within a date range",
    response_model=list[PriceResponse],
    responses={422: {"model": ErrorResponse, "description": "date_from is after date_to"}},
)
async def get_prices_by_date(
    ticker: TickerQuery,
    service: PriceServiceDep,
    date_from: DateFromQuery = None,
    date_to: DateToQuery = None,
    limit: LimitQuery = None,
    offset: OffsetQuery = 0,
) -> list[PriceResponse]:
    """Prices with `date_from <= timestamp <= date_to`. Either bound may be omitted."""
    snapshots = await service.get_by_date_range(
        ticker, date_from=date_from, date_to=date_to, limit=limit, offset=offset
    )
    return [PriceResponse.model_validate(snapshot) for snapshot in snapshots]
