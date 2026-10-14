"""Interfaces the services depend on, so they can be tested with fakes."""

from collections.abc import Iterable
from decimal import Decimal
from typing import Protocol

from deribit_tracker.domain import PriceSnapshot, Ticker


class PriceSource(Protocol):
    async def get_index_price(self, ticker: Ticker) -> Decimal: ...


class PriceReader(Protocol):
    async def list_by_ticker(
        self,
        ticker: Ticker,
        *,
        date_from: int | None = None,
        date_to: int | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[PriceSnapshot]: ...

    async def get_latest(self, ticker: Ticker) -> PriceSnapshot | None: ...


class PriceWriter(Protocol):
    async def add_many(self, snapshots: Iterable[PriceSnapshot]) -> None: ...
