import asyncio
from typing import Any

from celery import Celery, Task

from deribit_tracker.clients.deribit import DeribitUnavailableError
from deribit_tracker.config import Settings
from deribit_tracker.domain import Ticker
from deribit_tracker.worker.collection import run_collection

COLLECT_TASK_NAME = "deribit_tracker.collect_index_prices"
RETRY_DELAY_SECONDS = 5
MAX_RETRIES = 3


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
        result = asyncio.run(run_collection(settings, requested))

        retryable = {
            ticker: error
            for ticker, error in result.failed.items()
            if isinstance(error, DeribitUnavailableError)
        }
        if retryable:
            # Retry only the tickers that failed, so already saved prices are not duplicated.
            raise task.retry(
                kwargs={"tickers": [ticker.value for ticker in retryable]},
                countdown=RETRY_DELAY_SECONDS,
                exc=next(iter(retryable.values())),
            )
        return {
            "saved": [snapshot.ticker.value for snapshot in result.saved],
            "failed": {ticker.value: str(error) for ticker, error in result.failed.items()},
        }

    return app
