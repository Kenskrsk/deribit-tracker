import json
from decimal import Decimal, InvalidOperation
from typing import Any

import aiohttp

from deribit_tracker.domain import Ticker


class DeribitError(Exception):
    """Deribit answered, but the answer is an error or has an unexpected shape."""


class DeribitUnavailableError(DeribitError):
    """Deribit could not be reached (network error, timeout, 5xx, rate limit). Worth retrying."""


# Statuses that describe a temporary condition rather than a bad request.
RETRYABLE_STATUSES = frozenset({408, 429})

# JSON-RPC error codes Deribit uses for temporary conditions (https://docs.deribit.com/articles/errors).
RETRYABLE_RPC_ERROR_CODES = frozenset(
    {
        10028,  # too_many_requests
        10040,  # retry
        10066,  # too_many_concurrent_requests
        11051,  # system_maintenance
        13028,  # temporarily_unavailable
        13888,  # timed_out
    }
)


class DeribitClient:
    """Thin async client for the public Deribit JSON-RPC over HTTP API."""

    INDEX_PRICE_METHOD = "public/get_index_price"

    def __init__(self, session: aiohttp.ClientSession, base_url: str) -> None:
        self._session = session
        self._base_url = base_url.rstrip("/")

    async def get_index_price(self, ticker: Ticker) -> Decimal:
        result = await self._call(self.INDEX_PRICE_METHOD, {"index_name": ticker.value})
        try:
            return Decimal(result["index_price"])
        except (KeyError, TypeError, InvalidOperation) as error:
            raise DeribitError(f"Unexpected index price payload for {ticker}: {result}") from error

    async def _call(self, method: str, params: dict[str, str]) -> dict[str, Any]:
        url = f"{self._base_url}/{method}"
        try:
            async with self._session.get(url, params=params) as response:
                if response.status >= 500 or response.status in RETRYABLE_STATUSES:
                    raise DeribitUnavailableError(f"Deribit returned HTTP {response.status}")
                body = await response.text()
        except (aiohttp.ClientError, TimeoutError) as error:
            raise DeribitUnavailableError(f"Deribit request failed: {error!r}") from error

        # Floats are parsed as Decimal so the price is stored exactly as Deribit sent it.
        try:
            payload = json.loads(body, parse_float=Decimal)
        except ValueError as error:
            raise DeribitError(f"Deribit returned non-JSON body for {method}") from error
        if not isinstance(payload, dict):
            raise DeribitError(f"Unexpected Deribit response for {method}: {payload!r}")
        if "error" in payload:
            rpc_error = payload["error"]
            code = rpc_error.get("code") if isinstance(rpc_error, dict) else None
            error_class = (
                DeribitUnavailableError if code in RETRYABLE_RPC_ERROR_CODES else DeribitError
            )
            raise error_class(f"Deribit error for {method}: {rpc_error}")
        if "result" not in payload:
            raise DeribitError(f"Deribit response without result for {method}: {payload}")
        result: dict[str, Any] = payload["result"]
        return result
