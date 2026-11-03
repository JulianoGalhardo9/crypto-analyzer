from datetime import datetime

import pandas as pd
from sqlalchemy.orm import Session, sessionmaker

from crypto_analyzer.config import AssetsConfig, QualityConfig, RegimeConfig
from crypto_analyzer.core.models import Analysis
from crypto_analyzer.infra.repositories import (
    load_closed_candles,
    load_fact_frame,
    load_last_candle_ts,
)
from crypto_analyzer.infra.tables import FactIndicador, FactRegime
from crypto_analyzer.pipeline.analysis import assemble_analysis

RESOLUTION = "1d"


class NoDataError(ValueError):
    """O gold ainda não tem dados do ativo (falta rodar coletar, processar e calcular)."""


def build_analysis(
    session_factory: sessionmaker[Session],
    assets: AssetsConfig,
    base: str,
    now: datetime,
    quality: QualityConfig,
    regime: RegimeConfig,
) -> Analysis:
    """Lê candles e gold do banco e monta a análise de hoje para um ativo (ex.: `SOL`)."""
    asset = next((a for a in assets.assets if a.symbol == base), None)
    if asset is None:
        raise KeyError(base)
    symbol = f"{base}-{assets.quote}"

    with session_factory() as session:
        candles = load_closed_candles(session, symbol, RESOLUTION)[["high", "low", "close"]]
        indicators = load_fact_frame(session, FactIndicador, symbol)
        regimes = load_fact_frame(session, FactRegime, symbol)
        last_candle_ts = load_last_candle_ts(session, symbol, RESOLUTION)

    if candles.empty or indicators.empty or regimes.empty or last_candle_ts is None:
        raise NoDataError(f"ainda não há dados calculados de {base}")

    return assemble_analysis(
        symbol=symbol,
        base=base,
        name=asset.name,
        article=asset.article,
        is_benchmark=base == assets.benchmark,
        frame=pd.concat([candles, indicators, regimes], axis=1, join="inner"),
        last_candle_ts=last_candle_ts,
        now=now,
        max_age_hours=quality.max_age_hours[RESOLUTION],
        regime_config=regime,
    )
