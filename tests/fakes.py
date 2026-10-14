from collections.abc import Iterable
from decimal import Decimal

from deribit_tracker.domain import PriceSnapshot, Ticker


class InMemoryPriceRepository:
    """Fake repository with the same semantics as PriceRepository."""

    def __init__(self, snapshots: Iterable[PriceSnapshot] = ()) -> None:
        self.snapshots = list(snapshots)

    async def add_many(self, snapshots: Iterable[PriceSnapshot]) -> None:
        self.snapshots.extend(snapshots)

    async def list_by_ticker(
        self,
        ticker: Ticker,
        *,
        date_from: int | None = None,
        date_to: int | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[PriceSnapshot]:
        matching = sorted(
            (
                item
                for item in self.snapshots
                if item.ticker == ticker
                and (date_from is None or item.timestamp >= date_from)
                and (date_to is None or item.timestamp <= date_to)
            ),
            key=lambda item: item.timestamp,
        )
        end = None if limit is None else offset + limit
        return matching[offset:end]

    async def get_latest(self, ticker: Ticker) -> PriceSnapshot | None:
        # Like ORDER BY timestamp DESC, id DESC: on equal timestamps the last inserted wins.
        matching = [item for item in reversed(self.snapshots) if item.ticker == ticker]
        return max(matching, key=lambda item: item.timestamp) if matching else None


class StubPriceSource:
    """Returns preset prices; raises preset errors."""

    def __init__(self, outcomes: dict[Ticker, Decimal | Exception]) -> None:
        self._outcomes = outcomes

    async def get_index_price(self, ticker: Ticker) -> Decimal:
        outcome = self._outcomes[ticker]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def snapshot(ticker: Ticker, price: str, timestamp: int) -> PriceSnapshot:
    return PriceSnapshot(ticker=ticker, price=Decimal(price), timestamp=timestamp)
