from datetime import UTC, datetime

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from crypto_analyzer.config import AssetInfo, AssetsConfig, load_regime_config
from crypto_analyzer.infra.db import make_session_factory
from crypto_analyzer.infra.repositories import save_raw_candles, upsert_silver_candles
from crypto_analyzer.infra.tables import DimAtivo, FactIndicador, FactRegime
from crypto_analyzer.pipeline.market_data import RawCandles
from crypto_analyzer.pipeline.process_gold import process_gold

pytestmark = pytest.mark.integration

ASSETS = AssetsConfig(
    quote="BRL",
    benchmark="BTC",
    assets=[AssetInfo(symbol="BTC", name="Bitcoin"), AssetInfo(symbol="SOL", name="Solana")],
)
DAYS = 400


def seed_silver(session: Session, symbol: str, seed: int) -> None:
    """Grava DAYS candles sintéticos; o último é marcado como parcial (dia em andamento)."""
    bronze_id = save_raw_candles(
        session,
        RawCandles(symbol, "1d", {}, {"t": []}, datetime(2026, 10, 28, tzinfo=UTC)),
    )
    rng = np.random.default_rng(seed)
    index = pd.date_range("2025-09-01", periods=DAYS, freq="D", tz="UTC", name="ts")
    close = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.02, DAYS))), index=index)
    frame = pd.DataFrame(
        {
            "open": close,
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "volume": 1.0,
            "is_partial": [False] * (DAYS - 1) + [True],
            "source_bronze_id": bronze_id,
        }
    )
    upsert_silver_candles(session, symbol, "1d", frame)
    session.commit()


def count(session: Session, model: type) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def test_gold_is_written_for_closed_candles_only(engine: Engine, session: Session) -> None:
    seed_silver(session, "BTC-BRL", seed=1)
    seed_silver(session, "SOL-BRL", seed=2)

    summaries = process_gold(make_session_factory(engine), ASSETS, load_regime_config())

    assert count(session, DimAtivo) == 2
    assert count(session, FactIndicador) == 2 * (DAYS - 1)  # o candle parcial fica de fora
    assert count(session, FactRegime) == 2 * (DAYS - 1)
    assert {s.symbol: s.days for s in summaries} == {"BTC-BRL": DAYS - 1, "SOL-BRL": DAYS - 1}


def test_nan_becomes_null_and_benchmark_has_no_self_correlation(
    engine: Engine, session: Session
) -> None:
    seed_silver(session, "BTC-BRL", seed=1)
    seed_silver(session, "SOL-BRL", seed=2)
    process_gold(make_session_factory(engine), ASSETS, load_regime_config())

    ids = dict(session.execute(select(DimAtivo.symbol, DimAtivo.id)).all())
    first_btc = session.scalars(
        select(FactIndicador)
        .where(FactIndicador.ativo_id == ids["BTC-BRL"])
        .order_by(FactIndicador.ts)
    ).first()
    btc_corr = session.scalars(
        select(FactIndicador.corr_btc_90).where(FactIndicador.ativo_id == ids["BTC-BRL"])
    ).all()
    sol_corr = session.scalars(
        select(FactIndicador.corr_btc_90).where(FactIndicador.ativo_id == ids["SOL-BRL"])
    ).all()

    assert first_btc is not None
    assert first_btc.sma_20 is None and first_btc.rsi_14 is None  # aquecimento vira NULL
    assert all(value is None for value in btc_corr)
    assert sum(value is not None for value in sol_corr) > 0


def test_processing_twice_does_not_duplicate_rows(engine: Engine, session: Session) -> None:
    seed_silver(session, "BTC-BRL", seed=1)
    seed_silver(session, "SOL-BRL", seed=2)
    factory = make_session_factory(engine)

    process_gold(factory, ASSETS, load_regime_config())
    process_gold(factory, ASSETS, load_regime_config())

    assert count(session, DimAtivo) == 2
    assert count(session, FactIndicador) == 2 * (DAYS - 1)
    assert count(session, FactRegime) == 2 * (DAYS - 1)


def test_missing_silver_data_is_reported_clearly(engine: Engine, session: Session) -> None:
    seed_silver(session, "BTC-BRL", seed=1)  # falta a SOL

    with pytest.raises(ValueError, match="SOL-BRL"):
        process_gold(make_session_factory(engine), ASSETS, load_regime_config())
