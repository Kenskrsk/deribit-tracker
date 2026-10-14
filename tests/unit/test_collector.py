from decimal import Decimal

from deribit_tracker.clients.deribit import DeribitUnavailableError
from deribit_tracker.domain import Ticker
from deribit_tracker.services.collector import PriceCollector
from tests.fakes import InMemoryPriceRepository, StubPriceSource, snapshot

NOW = 1_791_992_264


async def test_saves_all_tickers_with_fetch_time() -> None:
    repository = InMemoryPriceRepository()
    source = StubPriceSource(
        {Ticker.BTC_USD: Decimal("81747.9"), Ticker.ETH_USD: Decimal("2434.47")}
    )
    collector = PriceCollector(source, repository, clock=lambda: NOW)

    result = await collector.collect(list(Ticker))

    expected = [
        snapshot(Ticker.BTC_USD, "81747.9", NOW),
        snapshot(Ticker.ETH_USD, "2434.47", NOW),
    ]
    assert repository.snapshots == expected
    assert result.saved == expected
    assert result.failed == {}


async def test_one_failing_ticker_does_not_block_the_other() -> None:
    error = DeribitUnavailableError("timeout")
    repository = InMemoryPriceRepository()
    source = StubPriceSource({Ticker.BTC_USD: error, Ticker.ETH_USD: Decimal("2434.47")})
    collector = PriceCollector(source, repository, clock=lambda: NOW)

    result = await collector.collect(list(Ticker))

    assert repository.snapshots == [snapshot(Ticker.ETH_USD, "2434.47", NOW)]
    assert result.failed == {Ticker.BTC_USD: error}


async def test_nothing_written_when_everything_fails() -> None:
    repository = InMemoryPriceRepository()
    source = StubPriceSource({ticker: DeribitUnavailableError("down") for ticker in Ticker})
    collector = PriceCollector(source, repository, clock=lambda: NOW)

    result = await collector.collect(list(Ticker))

    assert repository.snapshots == []
    assert set(result.failed) == set(Ticker)
