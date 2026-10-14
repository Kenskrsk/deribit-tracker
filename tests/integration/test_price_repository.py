from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from deribit_tracker.domain import Ticker
from deribit_tracker.repositories.prices import PriceRepository
from tests.fakes import snapshot

pytestmark = pytest.mark.integration

BTC = Ticker.BTC_USD
ETH = Ticker.ETH_USD


@pytest.fixture
async def repository(db_session: AsyncSession) -> PriceRepository:
    repo = PriceRepository(db_session)
    await repo.add_many(
        [
            snapshot(BTC, "102", 180),
            snapshot(BTC, "100", 60),
            snapshot(ETH, "10", 60),
            snapshot(BTC, "101", 120),
        ]
    )
    await db_session.commit()
    return repo


async def test_list_returns_ticker_history_in_time_order(repository: PriceRepository) -> None:
    history = await repository.list_by_ticker(BTC)

    assert [(item.timestamp, item.price) for item in history] == [
        (60, Decimal("100")),
        (120, Decimal("101")),
        (180, Decimal("102")),
    ]


async def test_list_filters_by_inclusive_date_range(repository: PriceRepository) -> None:
    history = await repository.list_by_ticker(BTC, date_from=60, date_to=120)

    assert [item.timestamp for item in history] == [60, 120]


async def test_list_paginates(repository: PriceRepository) -> None:
    history = await repository.list_by_ticker(BTC, limit=2, offset=1)

    assert [item.timestamp for item in history] == [120, 180]


async def test_latest_returns_newest_snapshot(repository: PriceRepository) -> None:
    assert await repository.get_latest(BTC) == snapshot(BTC, "102", 180)


async def test_latest_is_none_for_ticker_without_data(db_session: AsyncSession) -> None:
    assert await PriceRepository(db_session).get_latest(ETH) is None


async def test_price_precision_is_preserved(db_session: AsyncSession) -> None:
    repo = PriceRepository(db_session)
    await repo.add_many([snapshot(BTC, "81747.12345678", 1)])
    await db_session.commit()

    latest = await repo.get_latest(BTC)

    assert latest is not None
    assert latest.price == Decimal("81747.12345678")


async def test_latest_prefers_last_inserted_on_equal_timestamps(db_session: AsyncSession) -> None:
    repo = PriceRepository(db_session)
    await repo.add_many([snapshot(BTC, "1", 60)])
    await repo.add_many([snapshot(BTC, "2", 60)])
    await db_session.commit()

    assert await repo.get_latest(BTC) == snapshot(BTC, "2", 60)
