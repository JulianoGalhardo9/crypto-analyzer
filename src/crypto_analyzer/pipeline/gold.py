from collections.abc import Mapping
from dataclasses import dataclass

import pandas as pd

from crypto_analyzer.config import RegimeConfig
from crypto_analyzer.core.indicators import (
    atr,
    bollinger,
    ema,
    log_returns,
    macd,
    rolling_correlation,
    rsi,
    sma,
)
from crypto_analyzer.core.regime import compute_regimes

# Os parâmetros fazem parte do nome das colunas de fact_indicador (ver infra/tables.py).
CORRELATION_WINDOW = 90
INDICATOR_COLUMNS = [
    "sma_20",
    "sma_50",
    "sma_200",
    "ema_12",
    "ema_26",
    "rsi_14",
    "macd",
    "macd_signal",
    "macd_histogram",
    "atr_14",
    "bb_lower",
    "bb_middle",
    "bb_upper",
    "corr_btc_90",
]
REGIME_COLUMNS = ["volatility", "volatility_percentile", "raw_regime", "regime"]


@dataclass(frozen=True)
class GoldFrames:
    indicators: pd.DataFrame
    regimes: pd.DataFrame


def compute_indicators(candles: pd.DataFrame, benchmark_close: pd.Series | None) -> pd.DataFrame:
    """Todos os indicadores de um ativo, um por coluna, indexados por `ts`.

    `candles` precisa de high, low e close (só candles fechados). `benchmark_close` é o
    fechamento do ativo de referência; `None` (ou o próprio ativo) deixa a correlação nula.
    """
    close, high, low = candles["close"], candles["high"], candles["low"]
    macd_frame = macd(close, 12, 26, 9)
    bands = bollinger(close, 20, 2.0)
    correlation = (
        rolling_correlation(log_returns(close), log_returns(benchmark_close), CORRELATION_WINDOW)
        if benchmark_close is not None
        else pd.Series(dtype="float64")
    )
    frame = pd.DataFrame(
        {
            "sma_20": sma(close, 20),
            "sma_50": sma(close, 50),
            "sma_200": sma(close, 200),
            "ema_12": ema(close, 12),
            "ema_26": ema(close, 26),
            "rsi_14": rsi(close, 14),
            "macd": macd_frame["macd"],
            "macd_signal": macd_frame["signal"],
            "macd_histogram": macd_frame["histogram"],
            "atr_14": atr(high, low, close, 14),
            "bb_lower": bands["lower"],
            "bb_middle": bands["middle"],
            "bb_upper": bands["upper"],
            # reindex: a correlação só existe nas datas em comum com o BTC; no resto fica NaN
            "corr_btc_90": correlation.reindex(close.index),
        },
        index=close.index,
    )
    return frame[INDICATOR_COLUMNS]


def compute_gold(
    candles: Mapping[str, pd.DataFrame], benchmark: str, regime_config: RegimeConfig
) -> dict[str, GoldFrames]:
    """Candles fechados de cada par -> indicadores e regimes de cada par."""
    benchmark_close = candles[benchmark]["close"]
    return {
        symbol: GoldFrames(
            indicators=compute_indicators(frame, benchmark_close if symbol != benchmark else None),
            regimes=compute_regimes(frame["close"], **regime_config.model_dump()).rename(
                columns={"percentile": "volatility_percentile"}
            )[REGIME_COLUMNS],
        )
        for symbol, frame in candles.items()
    }
