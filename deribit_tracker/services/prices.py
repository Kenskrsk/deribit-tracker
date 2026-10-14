from deribit_tracker.domain import PriceSnapshot, Ticker
from deribit_tracker.services.ports import PriceReader


class PriceNotFoundError(Exception):
    def __init__(self, ticker: Ticker) -> None:
        super().__init__(f"No prices stored for {ticker.value} yet")
        self.ticker = ticker


class InvalidDateRangeError(ValueError):
    pass


class PriceQueryService:
    """Read-side use cases exposed by the HTTP API."""

    def __init__(self, reader: PriceReader) -> None:
        self._reader = reader

    async def get_history(
        self, ticker: Ticker, *, limit: int | None = None, offset: int = 0
    ) -> list[PriceSnapshot]:
        return await self._reader.list_by_ticker(ticker, limit=limit, offset=offset)

    async def get_latest(self, ticker: Ticker) -> PriceSnapshot:
        snapshot = await self._reader.get_latest(ticker)
        if snapshot is None:
            raise PriceNotFoundError(ticker)
        return snapshot

    async def get_by_date_range(
        self,
        ticker: Ticker,
        *,
        date_from: int | None = None,
        date_to: int | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[PriceSnapshot]:
        if date_from is not None and date_to is not None and date_from > date_to:
            raise InvalidDateRangeError("date_from must not be greater than date_to")
        return await self._reader.list_by_ticker(
            ticker, date_from=date_from, date_to=date_to, limit=limit, offset=offset
        )
