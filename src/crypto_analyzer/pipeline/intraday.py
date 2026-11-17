"""Atualização dos candles de 1h (DAG intraday_refresh): quem atualizar e a atualização em si."""

import logging
from datetime import datetime

from sqlalchemy.orm import Session, sessionmaker

from crypto_analyzer.config import AssetsConfig, QualityConfig, RegimeConfig
from crypto_analyzer.core.models import Regime
from crypto_analyzer.core.refresh import refresh_due
from crypto_analyzer.infra.repositories import load_last_fetch, load_latest_regime
from crypto_analyzer.pipeline.bronze import collect_candles
from crypto_analyzer.pipeline.process import ProcessSummary, process_silver

logger = logging.getLogger(__name__)

HOURLY = "1h"


def symbols_due_for_refresh(
    session_factory: sessionmaker[Session],
    assets: AssetsConfig,
    now: datetime,
    regime_config: RegimeConfig,
) -> list[str]:
    """Pares cujos candles de 1h já devem ser atualizados, pelo regime atual de cada um."""
    due = []
    with session_factory() as session:
        for symbol in assets.symbols:
            stored = load_latest_regime(session, symbol)
            regime = Regime(stored) if stored is not None else None
            last_fetch = load_last_fetch(session, symbol, HOURLY)
            is_due = refresh_due(regime, last_fetch, now, regime_config.refresh_hours)
            logger.info(
                "intraday: %s regime=%s última coleta 1h=%s -> %s",
                symbol,
                regime,
                last_fetch,
                "atualizar" if is_due else "ainda não",
            )
            if is_due:
                due.append(symbol)
    return due


def refresh_hourly(
    session_factory: sessionmaker[Session],
    symbol: str,
    now: datetime,
    quality: QualityConfig,
    countback: int,
) -> ProcessSummary:
    """API -> bronze -> silver dos candles de 1h de um par (idempotente na silver)."""
    collect_candles(session_factory, [symbol], HOURLY, to=now, countback=countback)
    [summary] = process_silver(session_factory, [symbol], HOURLY, now, quality)
    return summary
