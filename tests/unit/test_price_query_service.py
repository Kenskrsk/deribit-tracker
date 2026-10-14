import pytest

from deribit_tracker.domain import Ticker
from deribit_tracker.services.prices import (
    InvalidDateRangeError,
    PriceNotFoundError,
    PriceQueryService,
)
from tests.fakes import InMemoryPriceRepository, snapshot

BTC = Ticker.BTC_USD
ETH = Ticker.ETH_USD


@pytest.fixture
def service() -> PriceQueryService:
    return PriceQueryService(
        InMemoryPriceRepository(
            [
                snapshot(BTC, "100", 60),
                snapshot(ETH, "10", 60),
                snapshot(BTC, "101", 120),
                snapshot(BTC, "102", 180),
            ]
        )
    )


async def test_history_returns_only_requested_ticker(service: PriceQueryService) -> None:
    history = await service.get_history(BTC)

    assert [item.timestamp for item in history] == [60, 120, 180]
    assert all(item.ticker == BTC for item in history)


async def test_history_pagination(service: PriceQueryService) -> None:
    page = await service.get_history(BTC, limit=1, offset=1)

    assert [item.timestamp for item in page] == [120]


async def test_latest_returns_newest_price(service: PriceQueryService) -> None:
    latest = await service.get_latest(BTC)

    assert latest == snapshot(BTC, "102", 180)


async def test_latest_without_data_raises_not_found() -> None:
    service = PriceQueryService(InMemoryPriceRepository())

    with pytest.raises(PriceNotFoundError):
        await service.get_latest(BTC)


async def test_date_range_is_inclusive(service: PriceQueryService) -> None:
    prices = await service.get_by_date_range(BTC, date_from=120, date_to=180)

    assert [item.timestamp for item in prices] == [120, 180]


async def test_date_range_rejects_reversed_bounds(service: PriceQueryService) -> None:
    with pytest.raises(InvalidDateRangeError):
        await service.get_by_date_range(BTC, date_from=180, date_to=60)
