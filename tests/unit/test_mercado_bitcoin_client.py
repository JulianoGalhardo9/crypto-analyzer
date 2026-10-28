import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from crypto_analyzer.infra.mercado_bitcoin import USER_AGENT, MercadoBitcoinClient
from crypto_analyzer.pipeline.market_data import MarketDataError

pytestmark = pytest.mark.anyio

FIXTURE = Path(__file__).parent.parent / "fixtures" / "candles_sol_brl_1d.json"
TO = datetime(2026, 10, 28, tzinfo=UTC)


class Sleeps:
    """Records requested waits instead of really sleeping."""

    def __init__(self) -> None:
        self.delays: list[float] = []

    async def __call__(self, delay: float) -> None:
        self.delays.append(delay)


def make_client(
    handler: httpx.MockTransport | None = None,
    *,
    responses: list[httpx.Response] | None = None,
    sleeps: Sleeps | None = None,
    max_retries: int = 4,
    backoff_base: float = 1.0,
) -> tuple[MercadoBitcoinClient, list[httpx.Request]]:
    seen: list[httpx.Request] = []
    queue = list(responses or [])

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return queue.pop(0)

    http = httpx.AsyncClient(
        base_url="https://example.test/api/v4",
        headers={"User-Agent": USER_AGENT},
        transport=handler or httpx.MockTransport(handle),
    )
    client = MercadoBitcoinClient(
        http_client=http,
        min_interval=0,
        max_retries=max_retries,
        backoff_base=backoff_base,
        sleep=sleeps or Sleeps(),
    )
    return client, seen


def ok() -> httpx.Response:
    return httpx.Response(200, json=json.loads(FIXTURE.read_text()))


async def test_fetch_candles_returns_raw_payload_and_request_params() -> None:
    client, seen = make_client(responses=[ok()])

    raw = await client.fetch_candles("SOL-BRL", "1d", to=TO, countback=3)

    assert raw.payload == json.loads(FIXTURE.read_text())
    assert raw.symbol == "SOL-BRL"
    assert raw.params == {
        "symbol": "SOL-BRL",
        "resolution": "1d",
        "to": int(TO.timestamp()),
        "countback": 3,
    }
    assert raw.fetched_at.tzinfo is not None
    assert seen[0].url.path == "/api/v4/candles"
    assert seen[0].headers["User-Agent"] == USER_AGENT


async def test_optional_params_are_omitted_when_not_given() -> None:
    client, seen = make_client(responses=[ok()])

    await client.fetch_candles("BTC-BRL", "1h", to=TO)

    assert set(seen[0].url.params) == {"symbol", "resolution", "to"}


async def test_naive_datetime_is_rejected() -> None:
    client, _ = make_client(responses=[])

    with pytest.raises(ValueError, match="timezone-aware"):
        await client.fetch_candles("BTC-BRL", "1d", to=datetime(2026, 10, 28))  # noqa: DTZ001


async def test_retries_temporary_errors_with_exponential_backoff() -> None:
    sleeps = Sleeps()
    client, seen = make_client(
        responses=[httpx.Response(503), httpx.Response(503), ok()],
        sleeps=sleeps,
        backoff_base=1.0,
    )

    await client.fetch_candles("SOL-BRL", "1d", to=TO, countback=3)

    assert len(seen) == 3
    assert sleeps.delays == [1.0, 2.0]


async def test_retry_after_header_wins_over_backoff() -> None:
    sleeps = Sleeps()
    client, _ = make_client(
        responses=[httpx.Response(429, headers={"Retry-After": "7"}), ok()], sleeps=sleeps
    )

    await client.fetch_candles("SOL-BRL", "1d", to=TO)

    assert sleeps.delays == [7.0]


async def test_gives_up_after_max_retries() -> None:
    client, seen = make_client(responses=[httpx.Response(500)] * 3, max_retries=2)

    with pytest.raises(MarketDataError, match="HTTP 500"):
        await client.fetch_candles("SOL-BRL", "1d", to=TO)

    assert len(seen) == 3


async def test_does_not_retry_client_errors() -> None:
    client, seen = make_client(responses=[httpx.Response(403, text="forbidden")])

    with pytest.raises(MarketDataError, match="HTTP 403"):
        await client.fetch_candles("SOL-BRL", "1d", to=TO)

    assert len(seen) == 1


async def test_transport_errors_are_retried() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ConnectError("boom", request=request)
        return ok()

    client, _ = make_client(httpx.MockTransport(handler))

    raw = await client.fetch_candles("SOL-BRL", "1d", to=TO)

    assert calls == 2
    assert "t" in raw.payload


async def test_non_json_body_is_an_error() -> None:
    client, _ = make_client(responses=[httpx.Response(200, text="<html>")])

    with pytest.raises(MarketDataError, match="not valid JSON"):
        await client.fetch_candles("SOL-BRL", "1d", to=TO)


async def test_requests_are_spaced_by_min_interval() -> None:
    now = 100.0
    sleeps = Sleeps()

    def clock() -> float:
        return now

    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return ok()

    http = httpx.AsyncClient(
        base_url="https://example.test/api/v4", transport=httpx.MockTransport(handle)
    )
    client = MercadoBitcoinClient(http_client=http, min_interval=1.0, sleep=sleeps, clock=clock)

    await client.fetch_candles("SOL-BRL", "1d", to=TO)
    await client.fetch_candles("SOL-BRL", "1d", to=TO)

    assert sleeps.delays == [1.0]
