import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from crypto_analyzer.infra.db import make_session_factory
from crypto_analyzer.infra.tables import BronzeCandlesRaw
from crypto_analyzer.pipeline.bronze import ingest_candles
from crypto_analyzer.pipeline.market_data import MarketDataError, RawCandles

pytestmark = pytest.mark.integration

FIXTURE = Path(__file__).parent.parent / "fixtures" / "candles_sol_brl_1d.json"
TO = datetime(2026, 10, 28, tzinfo=UTC)


class FakeClient:
    """Fake de MarketDataClient: devolve a fixture e falha para os pares indicados."""

    def __init__(self, failing: set[str] | None = None) -> None:
        self.failing = failing or set()
        self.calls: list[str] = []

    async def fetch_candles(
        self,
        symbol: str,
        resolution: str,
        *,
        to: datetime,
        from_: datetime | None = None,
        countback: int | None = None,
    ) -> RawCandles:
        self.calls.append(symbol)
        if symbol in self.failing:
            raise MarketDataError("falha simulada")
        return RawCandles(
            symbol=symbol,
            resolution=resolution,
            params={"symbol": symbol, "resolution": resolution, "countback": countback or 0},
            payload=json.loads(FIXTURE.read_text()),
            fetched_at=datetime.now(UTC),
        )


@pytest.mark.anyio
async def test_ingest_saves_one_row_per_symbol(engine: Engine, session: Session) -> None:
    client = FakeClient()

    saved = await ingest_candles(
        client, make_session_factory(engine), ["BTC-BRL", "SOL-BRL"], "1d", to=TO, countback=3
    )

    assert client.calls == ["BTC-BRL", "SOL-BRL"]
    assert set(saved) == {"BTC-BRL", "SOL-BRL"}
    rows = session.scalars(select(BronzeCandlesRaw).order_by(BronzeCandlesRaw.id)).all()
    assert [r.symbol for r in rows] == ["BTC-BRL", "SOL-BRL"]
    assert rows[0].payload == json.loads(FIXTURE.read_text())


@pytest.mark.anyio
async def test_failure_keeps_what_was_already_saved(engine: Engine, session: Session) -> None:
    client = FakeClient(failing={"ETH-BRL"})

    with pytest.raises(MarketDataError):
        await ingest_candles(
            client,
            make_session_factory(engine),
            ["BTC-BRL", "ETH-BRL", "SOL-BRL"],
            "1d",
            to=TO,
            countback=3,
        )

    rows = session.scalars(select(BronzeCandlesRaw)).all()
    assert [r.symbol for r in rows] == ["BTC-BRL"]
