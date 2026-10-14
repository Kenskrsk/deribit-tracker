from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from deribit_tracker.db.models import PriceRecord
from deribit_tracker.domain import PriceSnapshot, Ticker


class PriceRepository:
    """Reads and writes price snapshots. Transactions are managed by the caller."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_many(self, snapshots: Iterable[PriceSnapshot]) -> None:
        self._session.add_all(
            PriceRecord(ticker=item.ticker.value, price=item.price, timestamp=item.timestamp)
            for item in snapshots
        )
        await self._session.flush()

    async def list_by_ticker(
        self,
        ticker: Ticker,
        *,
        date_from: int | None = None,
        date_to: int | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[PriceSnapshot]:
        """Snapshots of a ticker in chronological order, optionally within [date_from, date_to]."""
        query = select(PriceRecord).where(PriceRecord.ticker == ticker.value)
        if date_from is not None:
            query = query.where(PriceRecord.timestamp >= date_from)
        if date_to is not None:
            query = query.where(PriceRecord.timestamp <= date_to)
        query = query.order_by(PriceRecord.timestamp, PriceRecord.id).offset(offset).limit(limit)

        records = await self._session.scalars(query)
        return [self._to_snapshot(record) for record in records]

    async def get_latest(self, ticker: Ticker) -> PriceSnapshot | None:
        query = (
            select(PriceRecord)
            .where(PriceRecord.ticker == ticker.value)
            .order_by(PriceRecord.timestamp.desc(), PriceRecord.id.desc())
            .limit(1)
        )
        record = await self._session.scalar(query)
        return self._to_snapshot(record) if record is not None else None

    @staticmethod
    def _to_snapshot(record: PriceRecord) -> PriceSnapshot:
        return PriceSnapshot(
            ticker=Ticker(record.ticker), price=record.price, timestamp=record.timestamp
        )
