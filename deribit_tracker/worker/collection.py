import aiohttp

from deribit_tracker.clients.deribit import DeribitClient
from deribit_tracker.config import Settings
from deribit_tracker.db.engine import build_engine, build_session_factory
from deribit_tracker.domain import Ticker
from deribit_tracker.repositories.prices import PriceRepository
from deribit_tracker.services.collector import CollectionResult, PriceCollector


async def run_collection(settings: Settings, tickers: list[Ticker]) -> CollectionResult:
    """Wire up the collector for one run: own HTTP session, own DB engine, one transaction.

    Everything is created and disposed inside the run because a Celery task calls this
    through `asyncio.run`, i.e. in a new event loop every time.
    """
    engine = build_engine(settings.database_url, pooled=False)
    session_factory = build_session_factory(engine)
    timeout = aiohttp.ClientTimeout(total=settings.deribit_request_timeout_seconds)
    try:
        async with (
            aiohttp.ClientSession(timeout=timeout) as http_session,
            session_factory() as db_session,
            db_session.begin(),
        ):
            collector = PriceCollector(
                source=DeribitClient(http_session, settings.deribit_base_url),
                writer=PriceRepository(db_session),
            )
            return await collector.collect(tickers)
    finally:
        await engine.dispose()
