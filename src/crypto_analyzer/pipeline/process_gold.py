import logging
from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd
from sqlalchemy.orm import Session, sessionmaker

from crypto_analyzer.config import AssetsConfig, RegimeConfig
from crypto_analyzer.core.models import RegimeChange
from crypto_analyzer.core.regime import regime_changes_after
from crypto_analyzer.infra.repositories import (
    load_closed_candles,
    load_last_gold_ts,
    upsert_ativos,
    upsert_gold,
)
from crypto_analyzer.pipeline.gold import compute_gold

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GoldSummary:
    symbol: str
    days: int
    indicator_rows_with_data: int
    latest_regime: str | None
    # Trocas do regime confirmado em dias que o gold ainda não tinha (para alertar).
    new_changes: list[RegimeChange] = field(default_factory=list)


def process_gold(
    session_factory: sessionmaker[Session],
    assets: AssetsConfig,
    regime_config: RegimeConfig,
    resolution: str = "1d",
) -> list[GoldSummary]:
    """Silver (candles fechados) -> gold (indicadores e regimes), idempotente.

    Calcula tudo em memória (o BTC é necessário para a correlação dos outros) e grava
    em uma transação; reexecutar atualiza as mesmas linhas em vez de duplicar.
    """
    with session_factory() as session:
        candles = {
            symbol: load_closed_candles(session, symbol, resolution) for symbol in assets.symbols
        }
        empty = [symbol for symbol, frame in candles.items() if frame.empty]
        if empty:
            raise ValueError(f"sem candles na silver para: {', '.join(empty)} (rode `processar`)")

        previous_last = {symbol: load_last_gold_ts(session, symbol) for symbol in candles}
        gold = compute_gold(candles, assets.benchmark_symbol, regime_config)
        ids = upsert_ativos(session, assets)
        for symbol, frames in gold.items():
            upsert_gold(session, ids[symbol], frames)
        session.commit()

    summaries = []
    for symbol, frames in gold.items():
        regimes = frames.regimes["regime"].dropna()
        summaries.append(
            GoldSummary(
                symbol=symbol,
                days=len(frames.indicators),
                indicator_rows_with_data=int(frames.indicators["sma_200"].notna().sum()),
                latest_regime=str(regimes.iloc[-1]) if not regimes.empty else None,
                new_changes=regime_changes_after(
                    frames.regimes["regime"], _timestamp(previous_last[symbol])
                ),
            )
        )
        logger.info("gold: %s calculado", symbol)
    return summaries


def _timestamp(moment: datetime | None) -> pd.Timestamp | None:
    return pd.Timestamp(moment).tz_convert("UTC") if moment is not None else None
