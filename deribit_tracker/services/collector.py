import asyncio
import logging
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from deribit_tracker.domain import PriceSnapshot, Ticker
from deribit_tracker.services.ports import PriceSource, PriceWriter

logger = logging.getLogger(__name__)


def current_unix_time() -> int:
    return int(time.time())


@dataclass(frozen=True, slots=True)
class CollectionResult:
    saved: list[PriceSnapshot] = field(default_factory=list)
    failed: dict[Ticker, Exception] = field(default_factory=dict)


class PriceCollector:
    """Fetches index prices for several tickers concurrently and stores the successful ones.

    All snapshots of one run share the timestamp of the moment the run started.
    A failure for one ticker does not prevent the others from being saved;
    failed tickers are reported back so the caller can decide whether to retry them.
    """

    def __init__(
        self,
        source: PriceSource,
        writer: PriceWriter,
        clock: Callable[[], int] = current_unix_time,
    ) -> None:
        self._source = source
        self._writer = writer
        self._clock = clock

    async def collect(self, tickers: Sequence[Ticker]) -> CollectionResult:
        fetched_at = self._clock()
        outcomes = await asyncio.gather(
            *(self._fetch(ticker, fetched_at) for ticker in tickers), return_exceptions=True
        )

        result = CollectionResult()
        for ticker, outcome in zip(tickers, outcomes, strict=True):
            if isinstance(outcome, PriceSnapshot):
                result.saved.append(outcome)
            elif isinstance(outcome, Exception):
                logger.warning("Failed to fetch %s: %s", ticker, outcome)
                result.failed[ticker] = outcome
            else:
                raise outcome

        if result.saved:
            await self._writer.add_many(result.saved)
        return result

    async def _fetch(self, ticker: Ticker, fetched_at: int) -> PriceSnapshot:
        price = await self._source.get_index_price(ticker)
        return PriceSnapshot(ticker=ticker, price=price, timestamp=fetched_at)
