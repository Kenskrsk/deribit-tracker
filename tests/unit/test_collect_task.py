from types import SimpleNamespace
from unittest.mock import patch

import asyncpg
import pytest
from celery import Task
from celery.exceptions import Retry
from sqlalchemy.exc import DBAPIError, IntegrityError, InterfaceError

from deribit_tracker.clients.deribit import DeribitError, DeribitUnavailableError
from deribit_tracker.config import Settings
from deribit_tracker.domain import Ticker
from deribit_tracker.services.collector import CollectionResult
from deribit_tracker.worker import celery_app as celery_app_module
from deribit_tracker.worker.celery_app import (
    COLLECT_TASK_NAME,
    create_celery_app,
    is_transient_db_error,
)
from tests.fakes import snapshot


def build_task(
    monkeypatch: pytest.MonkeyPatch, outcome: CollectionResult | Exception
) -> tuple[Task, list[list[Ticker]]]:
    """The collection task with `run_collection` replaced; also returns the tickers it got."""
    requested: list[list[Ticker]] = []

    async def fake_run_collection(_: Settings, tickers: list[Ticker]) -> CollectionResult:
        requested.append(tickers)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(celery_app_module, "run_collection", fake_run_collection)
    task: Task = create_celery_app(Settings()).tasks[COLLECT_TASK_NAME]
    return task, requested


def test_collects_all_tickers_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    saved = [snapshot(Ticker.BTC_USD, "1", 1), snapshot(Ticker.ETH_USD, "2", 1)]
    task, requested = build_task(monkeypatch, CollectionResult(saved=saved))

    outcome = task.run()

    assert requested == [list(Ticker)]
    assert outcome == {"saved": ["btc_usd", "eth_usd"], "failed": {}}


def test_retries_only_unavailable_tickers_without_expiry(monkeypatch: pytest.MonkeyPatch) -> None:
    error = DeribitUnavailableError("timeout")
    result = CollectionResult(
        saved=[snapshot(Ticker.ETH_USD, "2", 1)], failed={Ticker.BTC_USD: error}
    )
    task, _ = build_task(monkeypatch, result)

    with patch.object(task, "retry", side_effect=Retry()) as retry, pytest.raises(Retry):
        task.run()

    retry.assert_called_once_with(
        kwargs={"tickers": ["btc_usd"]}, countdown=5, exc=error, expires=None
    )


@pytest.mark.parametrize(("attempt", "expected_delay"), [(0, 5), (1, 10), (2, 20)])
def test_retry_delay_grows_exponentially(
    monkeypatch: pytest.MonkeyPatch, attempt: int, expected_delay: int
) -> None:
    result = CollectionResult(failed={Ticker.BTC_USD: DeribitUnavailableError("down")})
    task, _ = build_task(monkeypatch, result)
    request = SimpleNamespace(retries=attempt)

    with (
        patch.object(type(task), "request", request),
        patch.object(task, "retry", side_effect=Retry()) as retry,
        pytest.raises(Retry),
    ):
        task.run()

    assert retry.call_args.kwargs["countdown"] == expected_delay


def test_retries_all_tickers_when_database_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    error = ConnectionRefusedError("database is down")
    task, _ = build_task(monkeypatch, error)

    with patch.object(task, "retry", side_effect=Retry()) as retry, pytest.raises(Retry):
        task.run()

    retry.assert_called_once_with(
        kwargs={"tickers": ["btc_usd", "eth_usd"]}, countdown=5, exc=error, expires=None
    )


def test_does_not_retry_non_transient_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    result = CollectionResult(failed={Ticker.BTC_USD: DeribitError("bad payload")})
    task, _ = build_task(monkeypatch, result)

    with patch.object(task, "retry") as retry:
        outcome = task.run(tickers=["btc_usd"])

    retry.assert_not_called()
    assert outcome == {"saved": [], "failed": {"btc_usd": "bad payload"}}


def wrapped_db_error(cause: Exception, error_class: type[DBAPIError] = DBAPIError) -> DBAPIError:
    """Mimic SQLAlchemy's asyncpg dialect: the original error is kept as orig.__cause__."""
    orig = Exception(str(cause))
    orig.__cause__ = cause
    return error_class("INSERT ...", None, orig)


@pytest.mark.parametrize(
    "error",
    [
        ConnectionRefusedError("refused"),
        wrapped_db_error(asyncpg.exceptions.CannotConnectNowError("starting up")),
        wrapped_db_error(asyncpg.exceptions.TooManyConnectionsError("no slots")),
        wrapped_db_error(asyncpg.exceptions.ConnectionDoesNotExistError("closed")),
    ],
)
def test_transient_db_errors_are_recognised(error: Exception) -> None:
    assert is_transient_db_error(error)


@pytest.mark.parametrize(
    "error",
    [
        wrapped_db_error(asyncpg.exceptions.UniqueViolationError("dup"), IntegrityError),
        wrapped_db_error(asyncpg.exceptions.DataError("bad encoding"), InterfaceError),
        ValueError("bug"),
    ],
)
def test_permanent_errors_are_not_treated_as_transient(error: Exception) -> None:
    assert not is_transient_db_error(error)


def test_permanent_db_error_fails_the_task_without_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    error = wrapped_db_error(asyncpg.exceptions.UniqueViolationError("dup"), IntegrityError)
    task, _ = build_task(monkeypatch, error)

    with patch.object(task, "retry") as retry, pytest.raises(IntegrityError):
        task.run()

    retry.assert_not_called()
