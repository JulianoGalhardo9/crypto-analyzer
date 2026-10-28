from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol


class MarketDataError(Exception):
    """A fonte de dados falhou de um jeito que novas tentativas não resolvem."""


@dataclass(frozen=True)
class RawCandles:
    """Resposta de candles exatamente como chegou, mais os parâmetros usados na chamada."""

    symbol: str
    resolution: str
    params: Mapping[str, str | int]
    payload: dict[str, Any]
    fetched_at: datetime


class MarketDataClient(Protocol):
    """Interface pequena sobre a fonte de dados, para os testes usarem um fake."""

    async def fetch_candles(
        self,
        symbol: str,
        resolution: str,
        *,
        to: datetime,
        from_: datetime | None = None,
        countback: int | None = None,
    ) -> RawCandles: ...
