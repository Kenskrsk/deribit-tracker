import asyncio
from typing import Any

import asyncpg
from celery import Celery, Task
from sqlalchemy.exc import DBAPIError

from deribit_tracker.clients.deribit import DeribitUnavailableError
from deribit_tracker.config import Settings
from deribit_tracker.domain import Ticker
from deribit_tracker.worker.collection import run_collection

COLLECT_TASK_NAME = "deribit_tracker.collect_index_prices"
RETRY_BASE_DELAY_SECONDS = 5
MAX_RETRIES = 3

# asyncpg errors meaning "the server cannot serve you right now": starting up or shutting
# down, out of connection slots, connection dropped. SQLAlchemy wraps them in DBAPIError
# subclasses that also cover permanent errors (e.g. InterfaceError for bad input encoding),
# so they are recognised by the original asyncpg error kept as `__cause__`.
TRANSIENT_ASYNCPG_ERRORS = (
    asyncpg.exceptions.OperatorInterventionError,
    asyncpg.exceptions.InsufficientResourcesError,
    asyncpg.exceptions.PostgresConnectionError,
)


def is_transient_db_error(error: BaseException) -> bool:
    """True for database failures that are worth retrying."""
    if isinstance(error, OSError):  # server unreachable: refused, DNS, timeout
        return True
    if isinstance(error, DBAPIError):
        original = error.orig.__cause__ if error.orig is not None else None
        return error.connection_invalidated or isinstance(original, TRANSIENT_ASYNCPG_ERRORS)
    return False


def create_celery_app(settings: Settings) -> Celery:
    """Build a Celery app with the price collection task and its beat schedule."""
    app = Celery("deribit_tracker", broker=settings.redis_url)
    app.conf.update(
        timezone="UTC",
        task_serializer="json",
        accept_content=["json"],
        task_ignore_result=True,
        beat_schedule={
            "collect-index-prices": {
                "task": COLLECT_TASK_NAME,
                "schedule": settings.fetch_interval_seconds,
                # A run that waited longer than one interval is stale: the next one is due.
                "options": {"expires": settings.fetch_interval_seconds},
            }
        },
    )

    @app.task(name=COLLECT_TASK_NAME, bind=True, max_retries=MAX_RETRIES)  # type: ignore[untyped-decorator]
    def collect_index_prices(task: Task, tickers: list[str] | None = None) -> dict[str, Any]:
        requested = [Ticker(value) for value in tickers] if tickers else list(Ticker)
        try:
            result = asyncio.run(run_collection(settings, requested))
        except Exception as error:
            if not is_transient_db_error(error):
                raise
            # The transaction was rolled back, so nothing was saved: retry every ticker.
            raise _retry(task, requested, error) from error

        retryable = {
            ticker: error
            for ticker, error in result.failed.items()
            if isinstance(error, DeribitUnavailableError)
        }
        if retryable:
            # Retry only the tickers that failed, so already saved prices are not duplicated.
            raise _retry(task, list(retryable), next(iter(retryable.values())))
        return {
            "saved": [snapshot.ticker.value for snapshot in result.saved],
            "failed": {ticker.value: str(error) for ticker, error in result.failed.items()},
        }

    return app


def _retry(task: Task, tickers: list[Ticker], error: Exception) -> Exception:
    """Schedule a retry for `tickers` with exponential backoff (5 s, 10 s, 20 s)."""
    retry: Exception = task.retry(
        kwargs={"tickers": [ticker.value for ticker in tickers]},
        countdown=RETRY_BASE_DELAY_SECONDS * 2**task.request.retries,
        exc=error,
        # Celery copies the original absolute `expires` into retries; a retry scheduled
        # after that moment would be silently discarded, so retries do not expire.
        expires=None,
    )
    return retry
