from datetime import UTC, datetime

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from crypto_analyzer.config import load_regime_config
from crypto_analyzer.infra.db import make_session_factory
from crypto_analyzer.infra.tables import DimAtivo, FactIndicador, FactRegime
from crypto_analyzer.pipeline.process_gold import process_gold
from tests.integration.helpers import ASSETS, DAYS, seed_silver

pytestmark = pytest.mark.integration


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


def test_gold_rows_after_the_last_closed_candle_are_removed(
    engine: Engine, session: Session
) -> None:
    seed_silver(session, "BTC-BRL", seed=1)
    seed_silver(session, "SOL-BRL", seed=2)
    factory = make_session_factory(engine)
    process_gold(factory, ASSETS, load_regime_config())
    ativo_id = session.scalars(select(DimAtivo.id).where(DimAtivo.symbol == "SOL-BRL")).one()
    # simula um dia que já contou como fechado e voltou a ser parcial
    session.add(FactIndicador(ativo_id=ativo_id, ts=datetime(2030, 1, 1, tzinfo=UTC)))
    session.add(FactRegime(ativo_id=ativo_id, ts=datetime(2030, 1, 1, tzinfo=UTC)))
    session.commit()

    process_gold(factory, ASSETS, load_regime_config())

    assert count(session, FactIndicador) == 2 * (DAYS - 1)
    assert count(session, FactRegime) == 2 * (DAYS - 1)
