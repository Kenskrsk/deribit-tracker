import asyncio
from collections.abc import AsyncIterator
from decimal import Decimal

import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from deribit_tracker.clients.deribit import DeribitClient, DeribitError, DeribitUnavailableError
from deribit_tracker.domain import Ticker


class FakeDeribit:
    """Local HTTP server standing in for Deribit; each test sets the response."""

    def __init__(self) -> None:
        self.response: web.Response = web.json_response({"result": {"index_price": 1}})
        self.delay_seconds = 0.0
        self.received_params: list[dict[str, str]] = []

    async def handle_index_price(self, request: web.Request) -> web.Response:
        self.received_params.append(dict(request.query))
        await asyncio.sleep(self.delay_seconds)
        return self.response


@pytest.fixture
def fake_deribit() -> FakeDeribit:
    return FakeDeribit()


@pytest.fixture
async def client(fake_deribit: FakeDeribit) -> AsyncIterator[DeribitClient]:
    app = web.Application()
    app.router.add_get("/api/v2/public/get_index_price", fake_deribit.handle_index_price)
    async with TestServer(app) as server:
        timeout = aiohttp.ClientTimeout(total=0.5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            yield DeribitClient(session, str(server.make_url("/api/v2")))


async def test_returns_index_price_as_exact_decimal(
    client: DeribitClient, fake_deribit: FakeDeribit
) -> None:
    fake_deribit.response = web.Response(
        text='{"jsonrpc":"2.0","result":{"index_price":81747.91,"estimated_delivery_price":1}}',
        content_type="application/json",
    )

    price = await client.get_index_price(Ticker.BTC_USD)

    assert price == Decimal("81747.91")


async def test_sends_ticker_as_index_name(client: DeribitClient, fake_deribit: FakeDeribit) -> None:
    await client.get_index_price(Ticker.ETH_USD)

    assert fake_deribit.received_params == [{"index_name": "eth_usd"}]


async def test_json_rpc_error_raises_deribit_error(
    client: DeribitClient, fake_deribit: FakeDeribit
) -> None:
    fake_deribit.response = web.json_response(
        {"error": {"code": -32602, "message": "Invalid params"}}, status=400
    )

    with pytest.raises(DeribitError) as caught:
        await client.get_index_price(Ticker.BTC_USD)

    assert not isinstance(caught.value, DeribitUnavailableError)


@pytest.mark.parametrize("body", ['{"result": {}}', '{"jsonrpc": "2.0"}', "not json", "[]"])
async def test_unexpected_payload_raises_deribit_error(
    client: DeribitClient, fake_deribit: FakeDeribit, body: str
) -> None:
    fake_deribit.response = web.Response(text=body, content_type="application/json")

    with pytest.raises(DeribitError):
        await client.get_index_price(Ticker.BTC_USD)


@pytest.mark.parametrize("status", [408, 429, 500, 503])
async def test_temporary_http_errors_are_retryable(
    client: DeribitClient, fake_deribit: FakeDeribit, status: int
) -> None:
    fake_deribit.response = web.Response(status=status)

    with pytest.raises(DeribitUnavailableError):
        await client.get_index_price(Ticker.BTC_USD)


async def test_timeout_is_retryable(client: DeribitClient, fake_deribit: FakeDeribit) -> None:
    fake_deribit.delay_seconds = 1.0

    with pytest.raises(DeribitUnavailableError):
        await client.get_index_price(Ticker.BTC_USD)


async def test_connection_error_is_retryable() -> None:
    async with aiohttp.ClientSession() as session:
        client = DeribitClient(session, "http://127.0.0.1:9")

        with pytest.raises(DeribitUnavailableError):
            await client.get_index_price(Ticker.BTC_USD)
