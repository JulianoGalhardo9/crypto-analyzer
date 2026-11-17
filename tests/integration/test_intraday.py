from datetime import UTC, datetime, timedelta
from types import TracebackType

import pytest
from sqlalchemy import Engine, func, select, update
from sqlalchemy.orm import Session

from crypto_analyzer.config import QualityConfig, load_regime_config
from crypto_analyzer.core.models import Regime
from crypto_analyzer.infra.db import make_session_factory
from crypto_analyzer.infra.repositories import load_latest_regime, save_raw_candles
from crypto_analyzer.infra.tables import DimAtivo, FactRegime, SilverCandle
from crypto_analyzer.pipeline import bronze
from crypto_analyzer.pipeline.intraday import refresh_hourly, symbols_due_for_refresh
from crypto_analyzer.pipeline.market_data import RawCandles
from crypto_analyzer.pipeline.process_gold import process_gold
from tests.integration.helpers import ASSETS, seed_silver

pytestmark = pytest.mark.integration

NOW = datetime(2026, 11, 17, 12, 5, tzinfo=UTC)
QUALITY = QualityConfig(outlier_threshold=10.0, max_age_hours={"1d": 48, "1h": 8})


def prepare(engine: Engine, session: Session) -> dict[str, Regime]:
    seed_silver(session, "BTC-BRL", seed=1)
    seed_silver(session, "SOL-BRL", seed=2)
    process_gold(make_session_factory(engine), ASSETS, load_regime_config())
    return {s: Regime(load_latest_regime(session, s) or "high") for s in ASSETS.symbols}


def fetched(session: Session, symbol: str, at: datetime) -> None:
    save_raw_candles(session, RawCandles(symbol, "1h", {}, {"t": []}, at))
    session.commit()


def test_without_any_hourly_collection_everything_is_due(engine: Engine, session: Session) -> None:
    prepare(engine, session)

    due = symbols_due_for_refresh(make_session_factory(engine), ASSETS, NOW, load_regime_config())

    assert due == ["BTC-BRL", "SOL-BRL"]


def test_collected_in_this_hour_is_not_due(engine: Engine, session: Session) -> None:
    prepare(engine, session)
    for symbol in ASSETS.symbols:
        fetched(session, symbol, NOW - timedelta(minutes=2))

    assert (
        symbols_due_for_refresh(make_session_factory(engine), ASSETS, NOW, load_regime_config())
        == []
    )


def test_one_hour_later_only_agitated_assets_are_due(engine: Engine, session: Session) -> None:
    regimes = prepare(engine, session)
    assert regimes == {"BTC-BRL": Regime.NORMAL, "SOL-BRL": Regime.NORMAL}
    # A SOL passa a "alta" no último dia; o BTC continua "normal" (intervalo de 3 h).
    sol = session.scalar(select(DimAtivo.id).where(DimAtivo.symbol == "SOL-BRL"))
    last_day = session.scalar(select(func.max(FactRegime.ts)).where(FactRegime.ativo_id == sol))
    session.execute(
        update(FactRegime)
        .where(FactRegime.ativo_id == sol, FactRegime.ts == last_day)
        .values(regime="high")
    )
    for symbol in ASSETS.symbols:
        fetched(session, symbol, NOW - timedelta(hours=1))

    due = symbols_due_for_refresh(make_session_factory(engine), ASSETS, NOW, load_regime_config())

    assert due == ["SOL-BRL"]


def test_the_longest_interval_makes_everything_due(engine: Engine, session: Session) -> None:
    prepare(engine, session)
    longest = max(load_regime_config().refresh_hours.values())
    for symbol in ASSETS.symbols:
        fetched(session, symbol, NOW - timedelta(hours=longest))

    due = symbols_due_for_refresh(make_session_factory(engine), ASSETS, NOW, load_regime_config())

    assert due == ["BTC-BRL", "SOL-BRL"]


class HourlyClient:
    """Fake da API: 3 candles de 1h terminando na hora cheia anterior a `to`."""

    async def __aenter__(self) -> "HourlyClient":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None

    async def fetch_candles(
        self, symbol: str, resolution: str, *, to: datetime, countback: int
    ) -> RawCandles:
        last = int(to.replace(minute=0, second=0, microsecond=0).timestamp()) - 3600
        times = [last - 7200, last - 3600, last]
        prices = ["100.0", "101.0", "102.0"]
        payload = {"t": times, "o": prices, "h": prices, "l": prices, "c": prices, "v": prices}
        return RawCandles(symbol, resolution, {"countback": countback}, payload, to)


def test_refresh_writes_hourly_candles_to_silver_and_is_idempotent(
    engine: Engine, session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(bronze, "MercadoBitcoinClient", HourlyClient)
    factory = make_session_factory(engine)

    first = refresh_hourly(factory, "SOL-BRL", NOW, QUALITY, countback=72)
    refresh_hourly(factory, "SOL-BRL", NOW, QUALITY, countback=72)

    rows = session.execute(
        select(SilverCandle.ts, SilverCandle.is_partial).where(
            SilverCandle.symbol == "SOL-BRL", SilverCandle.resolution == "1h"
        )
    ).all()
    assert first.candles == 3
    assert len(rows) == 3  # duas coletas, nenhuma linha duplicada
    assert not any(partial for _, partial in rows)  # todos fecharam antes da coleta
