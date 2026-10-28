from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol


class MarketDataError(Exception):
    """The market data source failed in a way retries could not fix."""


@dataclass(frozen=True)
class RawCandles:
    """A candles response exactly as received, plus how it was requested."""

    symbol: str
    resolution: str
    params: Mapping[str, str | int]
    payload: dict[str, Any]
    fetched_at: datetime


class MarketDataClient(Protocol):
    """Small seam over the data source so tests can use a fake."""

    async def fetch_candles(
        self,
        symbol: str,
        resolution: str,
        *,
        to: datetime,
        from_: datetime | None = None,
        countback: int | None = None,
    ) -> RawCandles: ...
