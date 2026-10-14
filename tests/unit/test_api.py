from collections.abc import AsyncIterator

import httpx
import pytest
from fastapi import FastAPI

from deribit_tracker.api.app import create_app
from deribit_tracker.api.dependencies import get_price_service
from deribit_tracker.domain import Ticker
from deribit_tracker.services.prices import PriceQueryService
from tests.fakes import InMemoryPriceRepository, snapshot

BTC = Ticker.BTC_USD
ETH = Ticker.ETH_USD


@pytest.fixture
def repository() -> InMemoryPriceRepository:
    return InMemoryPriceRepository(
        [
            snapshot(BTC, "81747.9", 1_000),
            snapshot(BTC, "81800.12", 1_060),
            snapshot(ETH, "2434.47", 1_000),
            snapshot(BTC, "81900", 1_120),
        ]
    )


@pytest.fixture
def app(repository: InMemoryPriceRepository) -> FastAPI:
    application = create_app()
    application.dependency_overrides[get_price_service] = lambda: PriceQueryService(repository)
    return application


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client


@pytest.mark.parametrize("path", ["/prices", "/prices/latest", "/prices/by-date"])
async def test_ticker_is_required(client: httpx.AsyncClient, path: str) -> None:
    response = await client.get(path)

    assert response.status_code == 422


@pytest.mark.parametrize("path", ["/prices", "/prices/latest", "/prices/by-date"])
async def test_unknown_ticker_is_rejected(client: httpx.AsyncClient, path: str) -> None:
    response = await client.get(path, params={"ticker": "doge_usd"})

    assert response.status_code == 422


async def test_get_prices_returns_full_history(client: httpx.AsyncClient) -> None:
    response = await client.get("/prices", params={"ticker": "btc_usd"})

    assert response.status_code == 200
    assert response.json() == [
        {"ticker": "btc_usd", "price": 81747.9, "timestamp": 1_000},
        {"ticker": "btc_usd", "price": 81800.12, "timestamp": 1_060},
        {"ticker": "btc_usd", "price": 81900.0, "timestamp": 1_120},
    ]


async def test_get_prices_paginates(client: httpx.AsyncClient) -> None:
    response = await client.get("/prices", params={"ticker": "btc_usd", "limit": 2, "offset": 1})

    assert [item["timestamp"] for item in response.json()] == [1_060, 1_120]


@pytest.mark.parametrize("params", [{"limit": 0}, {"offset": -1}, {"offset": 2**63}])
async def test_get_prices_rejects_bad_pagination(
    client: httpx.AsyncClient, params: dict[str, int]
) -> None:
    response = await client.get("/prices", params={"ticker": "btc_usd", **params})

    assert response.status_code == 422


async def test_get_latest_price(client: httpx.AsyncClient) -> None:
    response = await client.get("/prices/latest", params={"ticker": "eth_usd"})

    assert response.status_code == 200
    assert response.json() == {"ticker": "eth_usd", "price": 2434.47, "timestamp": 1_000}


async def test_get_latest_price_without_data_returns_404(
    client: httpx.AsyncClient, repository: InMemoryPriceRepository
) -> None:
    repository.snapshots.clear()

    response = await client.get("/prices/latest", params={"ticker": "btc_usd"})

    assert response.status_code == 404
    assert response.json() == {"detail": "No prices stored for btc_usd yet"}


async def test_get_prices_by_date_range(client: httpx.AsyncClient) -> None:
    response = await client.get(
        "/prices/by-date", params={"ticker": "btc_usd", "date_from": 1_060, "date_to": 1_120}
    )

    assert response.status_code == 200
    assert [item["timestamp"] for item in response.json()] == [1_060, 1_120]


async def test_get_prices_by_date_with_open_end(client: httpx.AsyncClient) -> None:
    response = await client.get("/prices/by-date", params={"ticker": "btc_usd", "date_to": 1_000})

    assert [item["timestamp"] for item in response.json()] == [1_000]


async def test_get_prices_by_date_rejects_reversed_range(client: httpx.AsyncClient) -> None:
    response = await client.get(
        "/prices/by-date", params={"ticker": "btc_usd", "date_from": 2_000, "date_to": 1_000}
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "date_from must not be greater than date_to"}


@pytest.mark.parametrize("bound", ["date_from", "date_to"])
async def test_get_prices_by_date_rejects_out_of_range_timestamp(
    client: httpx.AsyncClient, bound: str
) -> None:
    response = await client.get("/prices/by-date", params={"ticker": "btc_usd", bound: 2**63})

    assert response.status_code == 422
