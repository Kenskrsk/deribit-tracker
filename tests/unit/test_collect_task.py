from unittest.mock import patch

import pytest
from celery import Task
from celery.exceptions import Retry

from deribit_tracker.clients.deribit import DeribitError, DeribitUnavailableError
from deribit_tracker.config import Settings
from deribit_tracker.domain import Ticker
from deribit_tracker.services.collector import CollectionResult
from deribit_tracker.worker import celery_app as celery_app_module
from deribit_tracker.worker.celery_app import (
    COLLECT_TASK_NAME,
    RETRY_DELAY_SECONDS,
    create_celery_app,
)
from tests.fakes import snapshot


def build_task(
    monkeypatch: pytest.MonkeyPatch, result: CollectionResult
) -> tuple[Task, list[list[Ticker]]]:
    """The collection task with `run_collection` replaced; also returns the tickers it got."""
    requested: list[list[Ticker]] = []

    async def fake_run_collection(_: Settings, tickers: list[Ticker]) -> CollectionResult:
        requested.append(tickers)
        return result

    monkeypatch.setattr(celery_app_module, "run_collection", fake_run_collection)
    task: Task = create_celery_app(Settings()).tasks[COLLECT_TASK_NAME]
    return task, requested


def test_collects_all_tickers_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    saved = [snapshot(Ticker.BTC_USD, "1", 1), snapshot(Ticker.ETH_USD, "2", 1)]
    task, requested = build_task(monkeypatch, CollectionResult(saved=saved))

    outcome = task.run()

    assert requested == [list(Ticker)]
    assert outcome == {"saved": ["btc_usd", "eth_usd"], "failed": {}}


def test_retries_only_unavailable_tickers(monkeypatch: pytest.MonkeyPatch) -> None:
    error = DeribitUnavailableError("timeout")
    result = CollectionResult(
        saved=[snapshot(Ticker.ETH_USD, "2", 1)], failed={Ticker.BTC_USD: error}
    )
    task, _ = build_task(monkeypatch, result)

    with patch.object(task, "retry", side_effect=Retry()) as retry, pytest.raises(Retry):
        task.run()

    retry.assert_called_once_with(
        kwargs={"tickers": ["btc_usd"]}, countdown=RETRY_DELAY_SECONDS, exc=error
    )


def test_does_not_retry_non_transient_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    result = CollectionResult(failed={Ticker.BTC_USD: DeribitError("bad payload")})
    task, _ = build_task(monkeypatch, result)

    with patch.object(task, "retry") as retry:
        outcome = task.run(tickers=["btc_usd"])

    retry.assert_not_called()
    assert outcome == {"saved": [], "failed": {"btc_usd": "bad payload"}}
