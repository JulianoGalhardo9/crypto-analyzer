import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from types import TracebackType
from typing import Any, Self

import httpx

from crypto_analyzer import __version__
from crypto_analyzer.pipeline.market_data import MarketDataError, RawCandles

BASE_URL = "https://api.mercadobitcoin.net/api/v4"
# The API answers 403 to the default "Python-urllib" User-Agent, so we identify ourselves.
USER_AGENT = f"crypto-analyzer/{__version__}"
# Failures worth retrying: rate limited or a temporary server problem.
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})

logger = logging.getLogger(__name__)


class MercadoBitcoinClient:
    """Async client for the public candles endpoint (implements MarketDataClient).

    The API allows 1 request/second, so calls are spaced by `min_interval`.
    Retryable failures wait `backoff_base * 2**attempt` seconds (or `Retry-After`).
    `sleep` and `clock` are injectable so tests never really wait.
    """

    def __init__(
        self,
        *,
        http_client: httpx.AsyncClient | None = None,
        min_interval: float = 1.0,
        max_retries: int = 4,
        backoff_base: float = 1.0,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._owns_http = http_client is None
        self._http = http_client or httpx.AsyncClient(
            base_url=BASE_URL, headers={"User-Agent": USER_AGENT}, timeout=30.0
        )
        self._min_interval = min_interval
        self._max_retries = max_retries
        self._backoff_base = backoff_base
        self._sleep = sleep
        self._clock = clock
        self._lock = asyncio.Lock()
        self._last_request_at: float | None = None

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    async def fetch_candles(
        self,
        symbol: str,
        resolution: str,
        *,
        to: datetime,
        from_: datetime | None = None,
        countback: int | None = None,
    ) -> RawCandles:
        params: dict[str, str | int] = {
            "symbol": symbol,
            "resolution": resolution,
            "to": _to_unix(to),
        }
        if from_ is not None:
            params["from"] = _to_unix(from_)
        if countback is not None:
            params["countback"] = countback

        payload = await self._get_json("/candles", params)
        return RawCandles(
            symbol=symbol,
            resolution=resolution,
            params=params,
            payload=payload,
            fetched_at=datetime.now(UTC),
        )

    async def _get_json(self, path: str, params: dict[str, str | int]) -> dict[str, Any]:
        for attempt in range(self._max_retries + 1):
            await self._throttle()
            try:
                response = await self._http.get(path, params=params)
            except httpx.TransportError as exc:
                if attempt == self._max_retries:
                    raise MarketDataError(f"request failed after retries: {exc!r}") from exc
                await self._backoff(attempt, retry_after=None, reason=repr(exc))
                continue

            if response.status_code in RETRYABLE_STATUS:
                if attempt == self._max_retries:
                    raise MarketDataError(
                        f"HTTP {response.status_code} after {attempt + 1} attempts"
                    )
                await self._backoff(
                    attempt,
                    retry_after=_parse_retry_after(response),
                    reason=f"HTTP {response.status_code}",
                )
                continue

            if response.status_code != httpx.codes.OK:
                raise MarketDataError(f"HTTP {response.status_code}: {response.text[:200]}")

            try:
                body = response.json()
            except ValueError as exc:
                raise MarketDataError("response was not valid JSON") from exc
            if not isinstance(body, dict):
                raise MarketDataError(f"expected a JSON object, got {type(body).__name__}")
            return body

        raise AssertionError("unreachable")  # pragma: no cover

    async def _throttle(self) -> None:
        async with self._lock:
            if self._last_request_at is not None:
                wait = self._last_request_at + self._min_interval - self._clock()
                if wait > 0:
                    await self._sleep(wait)
            self._last_request_at = self._clock()

    async def _backoff(self, attempt: int, *, retry_after: float | None, reason: str) -> None:
        delay = retry_after if retry_after is not None else self._backoff_base * 2**attempt
        logger.warning("retrying in %.1fs (attempt %d): %s", delay, attempt + 1, reason)
        await self._sleep(delay)


def _to_unix(moment: datetime) -> int:
    if moment.tzinfo is None:
        raise ValueError("datetimes must be timezone-aware (use UTC)")
    return int(moment.timestamp())


def _parse_retry_after(response: httpx.Response) -> float | None:
    value = response.headers.get("Retry-After")
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None
