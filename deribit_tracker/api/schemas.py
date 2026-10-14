from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer

from deribit_tracker.domain import Ticker

# Stored exactly as Decimal; rendered as a plain JSON number for API consumers.
JsonNumber = Annotated[Decimal, PlainSerializer(float, return_type=float, when_used="json")]


class PriceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ticker: Ticker = Field(examples=["btc_usd"])
    price: JsonNumber = Field(description="Deribit index price in USD", examples=[81747.9])
    timestamp: int = Field(description="Fetch time, UNIX seconds (UTC)", examples=[1791992264])


class ErrorResponse(BaseModel):
    detail: str
