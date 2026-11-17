from datetime import UTC, datetime

import pytest
from sqlalchemy import Engine, delete, func, select
from sqlalchemy.orm import Session

from crypto_analyzer.config import BacktestConfig, load_backtest_config, load_regime_config
from crypto_analyzer.core.backtest import run_backtest
from crypto_analyzer.core.models import Signal
from crypto_analyzer.core.regime import regime_changes_after
from crypto_analyzer.infra.db import make_session_factory
from crypto_analyzer.infra.repositories import load_closed_candles, load_fact_frame
from crypto_analyzer.infra.tables import DimAtivo, FactBacktest, FactIndicador, FactRegime
from crypto_analyzer.pipeline.process_gold import process_gold
from tests.integration.helpers import ASSETS, DAYS, seed_silver

pytestmark = pytest.mark.integration


def count(session: Session, model: type) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def test_gold_is_written_for_closed_candles_only(engine: Engine, session: Session) -> None:
    seed_silver(session, "BTC-BRL", seed=1)
    seed_silver(session, "SOL-BRL", seed=2)

    summaries = process_gold(
        make_session_factory(engine), ASSETS, load_regime_config(), load_backtest_config()
    )

    assert count(session, DimAtivo) == 2
    assert count(session, FactIndicador) == 2 * (DAYS - 1)  # o candle parcial fica de fora
    assert count(session, FactRegime) == 2 * (DAYS - 1)
    assert {s.symbol: s.days for s in summaries} == {"BTC-BRL": DAYS - 1, "SOL-BRL": DAYS - 1}


def test_nan_becomes_null_and_benchmark_has_no_self_correlation(
    engine: Engine, session: Session
) -> None:
    seed_silver(session, "BTC-BRL", seed=1)
    seed_silver(session, "SOL-BRL", seed=2)
    process_gold(make_session_factory(engine), ASSETS, load_regime_config(), load_backtest_config())

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

    process_gold(factory, ASSETS, load_regime_config(), load_backtest_config())
    process_gold(factory, ASSETS, load_regime_config(), load_backtest_config())

    assert count(session, DimAtivo) == 2
    assert count(session, FactIndicador) == 2 * (DAYS - 1)
    assert count(session, FactRegime) == 2 * (DAYS - 1)


def test_missing_silver_data_is_reported_clearly(engine: Engine, session: Session) -> None:
    seed_silver(session, "BTC-BRL", seed=1)  # falta a SOL

    with pytest.raises(ValueError, match="SOL-BRL"):
        process_gold(
            make_session_factory(engine), ASSETS, load_regime_config(), load_backtest_config()
        )


def test_gold_rows_after_the_last_closed_candle_are_removed(
    engine: Engine, session: Session
) -> None:
    seed_silver(session, "BTC-BRL", seed=1)
    seed_silver(session, "SOL-BRL", seed=2)
    factory = make_session_factory(engine)
    process_gold(factory, ASSETS, load_regime_config(), load_backtest_config())
    ativo_id = session.scalars(select(DimAtivo.id).where(DimAtivo.symbol == "SOL-BRL")).one()
    # simula um dia que já contou como fechado e voltou a ser parcial
    session.add(FactIndicador(ativo_id=ativo_id, ts=datetime(2030, 1, 1, tzinfo=UTC)))
    session.add(FactRegime(ativo_id=ativo_id, ts=datetime(2030, 1, 1, tzinfo=UTC)))
    session.commit()

    process_gold(factory, ASSETS, load_regime_config(), load_backtest_config())

    assert count(session, FactIndicador) == 2 * (DAYS - 1)
    assert count(session, FactRegime) == 2 * (DAYS - 1)


def test_only_regime_changes_in_days_new_to_the_gold_are_reported(
    engine: Engine, session: Session
) -> None:
    seed_silver(session, "BTC-BRL", seed=1)
    seed_silver(session, "SOL-BRL", seed=2)
    factory = make_session_factory(engine)

    first = process_gold(factory, ASSETS, load_regime_config(), load_backtest_config())
    assert all(s.new_changes == [] for s in first)  # primeira carga: nada é novidade

    # Simula que o gold tinha sido calculado só até 120 dias atrás.
    regimes = {
        symbol: load_fact_frame(session, FactRegime, symbol)["regime"]
        for symbol in ("BTC-BRL", "SOL-BRL")
    }
    cutoff = regimes["BTC-BRL"].index[-121]
    session.execute(delete(FactRegime).where(FactRegime.ts > cutoff.to_pydatetime()))
    session.commit()

    second = {
        s.symbol: s.new_changes
        for s in process_gold(factory, ASSETS, load_regime_config(), load_backtest_config())
    }

    expected = {s: regime_changes_after(r, cutoff) for s, r in regimes.items()}
    assert second == expected
    assert sum(len(c) for c in second.values()) > 0  # o cenário tem trocas de verdade
    assert all(c.ts > cutoff for changes in second.values() for c in changes)

    third = process_gold(factory, ASSETS, load_regime_config(), load_backtest_config())
    assert all(s.new_changes == [] for s in third)  # repetir o mesmo dia não realerta


def test_backtests_are_stored_per_asset_signal_and_horizon(
    engine: Engine, session: Session
) -> None:
    seed_silver(session, "BTC-BRL", seed=1)
    seed_silver(session, "SOL-BRL", seed=2)
    factory = make_session_factory(engine)
    config = BacktestConfig(min_sample=3, horizons_days=[7, 30])

    process_gold(factory, ASSETS, load_regime_config(), config)
    process_gold(factory, ASSETS, load_regime_config(), config)  # repetir não duplica

    rows = session.scalars(select(FactBacktest)).all()
    assert len(rows) == 2 * len(Signal) * 2
    # Comparação com o cálculo puro sobre os mesmos dados (candles fechados + indicadores).
    sol = session.scalar(select(DimAtivo.id).where(DimAtivo.symbol == "SOL-BRL"))
    indicators = load_fact_frame(session, FactIndicador, "SOL-BRL")
    close = load_closed_candles(session, "SOL-BRL", "1d")["close"]
    expected = {
        (str(r.signal), r.horizon_days): r
        for r in run_backtest(close, indicators["rsi_14"], indicators["sma_200"], [7, 30], 3)
    }
    for row in (r for r in rows if r.ativo_id == sol):
        pure = expected[(row.signal, row.horizon_days)]
        assert (row.raw_count, row.independent_count, row.evaluated_count) == (
            pure.raw_count,
            pure.independent_count,
            pure.evaluated_count,
        )
        assert row.enough_sample == pure.enough_sample and row.min_sample == 3
        assert row.mean_return == pytest.approx(pure.mean_return)
        assert row.data_until == close.index.max()

    # Horizonte removido do YAML: a linha antiga some.
    process_gold(
        factory, ASSETS, load_regime_config(), BacktestConfig(min_sample=3, horizons_days=[7])
    )
    assert session.scalar(select(func.count()).select_from(FactBacktest)) == 2 * len(Signal)
