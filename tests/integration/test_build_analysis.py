from datetime import UTC, datetime

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from crypto_analyzer.config import QualityConfig, load_regime_config
from crypto_analyzer.core.explainer import explain
from crypto_analyzer.core.models import Regime
from crypto_analyzer.infra.db import make_session_factory
from crypto_analyzer.pipeline.build_analysis import NoDataError, build_analysis
from crypto_analyzer.pipeline.process_gold import process_gold
from tests.integration.helpers import ASSETS, seed_silver

pytestmark = pytest.mark.integration

QUALITY = QualityConfig(outlier_threshold=10.0, max_age_hours={"1d": 48, "1h": 3})
# o último candle (parcial) começa em 2025-09-01 + 399 dias
LAST_PARTIAL_DAY = datetime(2026, 10, 5, tzinfo=UTC)


def prepare(engine: Engine, session: Session) -> None:
    seed_silver(session, "BTC-BRL", seed=1)
    seed_silver(session, "SOL-BRL", seed=2)
    process_gold(make_session_factory(engine), ASSETS, load_regime_config())


def test_analysis_is_built_from_the_database(engine: Engine, session: Session) -> None:
    prepare(engine, session)
    now = datetime(2026, 10, 5, 12, tzinfo=UTC)

    analysis = build_analysis(
        make_session_factory(engine), ASSETS, "SOL", now, QUALITY, load_regime_config()
    )

    assert analysis.symbol == "SOL-BRL" and analysis.name == "Solana"
    assert analysis.as_of == datetime(2026, 10, 4, tzinfo=UTC)  # o parcial fica de fora
    assert analysis.last_candle_ts == LAST_PARTIAL_DAY  # mas mede a idade do dado
    assert analysis.data_age_hours == pytest.approx(12.0) and not analysis.is_stale
    assert analysis.regime in set(Regime)
    assert analysis.corr_btc_90 is not None and not analysis.is_benchmark
    assert "SOL (Solana)" in explain(analysis)


def test_benchmark_is_flagged_and_has_no_correlation(engine: Engine, session: Session) -> None:
    prepare(engine, session)

    btc = build_analysis(
        make_session_factory(engine),
        ASSETS,
        "BTC",
        datetime(2026, 10, 5, 12, tzinfo=UTC),
        QUALITY,
        load_regime_config(),
    )

    assert btc.is_benchmark and btc.corr_btc_90 is None
    assert "Com o BTC" not in explain(btc)


def test_old_data_is_marked_stale(engine: Engine, session: Session) -> None:
    prepare(engine, session)

    analysis = build_analysis(
        make_session_factory(engine),
        ASSETS,
        "SOL",
        datetime(2026, 10, 12, tzinfo=UTC),  # 7 dias depois do candle mais recente
        QUALITY,
        load_regime_config(),
    )

    assert analysis.is_stale
    assert "os dados mais recentes são de 7 dias atrás" in explain(analysis)


def test_missing_gold_data_raises_no_data_error(engine: Engine, session: Session) -> None:
    with pytest.raises(NoDataError, match="SOL"):
        build_analysis(
            make_session_factory(engine),
            ASSETS,
            "SOL",
            datetime(2026, 10, 5, tzinfo=UTC),
            QUALITY,
            load_regime_config(),
        )


def test_unknown_asset_is_a_key_error(engine: Engine, session: Session) -> None:
    with pytest.raises(KeyError):
        build_analysis(
            make_session_factory(engine),
            ASSETS,
            "XRP",
            datetime(2026, 10, 5, tzinfo=UTC),
            QUALITY,
            load_regime_config(),
        )
