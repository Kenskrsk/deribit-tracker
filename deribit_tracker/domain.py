from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class Ticker(StrEnum):
    """Currency pairs whose Deribit index price is tracked."""

    BTC_USD = "btc_usd"
    ETH_USD = "eth_usd"


@dataclass(frozen=True, slots=True)
class PriceSnapshot:
    """Index price of a ticker at a moment in time (UNIX seconds, UTC)."""

    ticker: Ticker
    price: Decimal
    timestamp: int
