from datetime import datetime
from typing import Any

import pandas as pd

from crypto_analyzer.config import RegimeConfig
from crypto_analyzer.core.indicators import recent_extremes
from crypto_analyzer.core.models import Analysis, CorrelationLevel, Regime
from crypto_analyzer.core.regime import latest_percentile
from crypto_analyzer.core.trend import classify_trend

# Janela do "último ano" usada para comparar o presente com o histórico do próprio ativo.
YEAR = 365


def assemble_analysis(
    *,
    symbol: str,
    base: str,
    name: str,
    is_benchmark: bool,
    frame: pd.DataFrame,
    last_candle_ts: datetime,
    now: datetime,
    max_age_hours: float,
    regime_config: RegimeConfig,
) -> Analysis:
    """Junta candles e gold de um ativo (indexados por `ts`) no objeto `Analysis` de hoje.

    `frame` precisa ter high, low, close, os indicadores e os regimes, só de candles fechados.
    `last_candle_ts` é o candle mais recente, inclusive o parcial: mede o quão velho é o dado.
    """
    if frame.empty:
        raise ValueError(f"sem dados calculados para {symbol}")

    last = frame.iloc[-1]
    close = frame["close"]
    age_hours = (pd.Timestamp(now) - pd.Timestamp(last_candle_ts)).total_seconds() / 3600
    daily_moves = close.pct_change().abs().iloc[-YEAR:].dropna()
    corr_percentile = (
        None
        if is_benchmark
        else latest_percentile(frame["corr_btc_90"], YEAR, regime_config.min_history)
    )
    range_30 = recent_extremes(frame["high"], frame["low"], 30)
    range_90 = recent_extremes(frame["high"], frame["low"], 90)

    return Analysis(
        symbol=symbol,
        base=base,
        name=name,
        is_benchmark=is_benchmark,
        as_of=frame.index[-1].to_pydatetime(),
        last_candle_ts=last_candle_ts,
        data_age_hours=age_hours,
        is_stale=age_hours > max_age_hours,
        price=float(last["close"]),
        change_1d=_change(close, 1),
        change_7d=_change(close, 7),
        change_30d=_change(close, 30),
        trend=classify_trend(
            float(last["close"]), _optional(last["sma_50"]), _optional(last["sma_200"])
        ),
        sma_20=_optional(last["sma_20"]),
        sma_50=_optional(last["sma_50"]),
        sma_200=_optional(last["sma_200"]),
        rsi_14=_optional(last["rsi_14"]),
        macd=_optional(last["macd"]),
        macd_signal=_optional(last["macd_signal"]),
        macd_histogram=_optional(last["macd_histogram"]),
        atr_14=_optional(last["atr_14"]),
        bb_lower=_optional(last["bb_lower"]),
        bb_middle=_optional(last["bb_middle"]),
        bb_upper=_optional(last["bb_upper"]),
        volatility=_optional(last["volatility"]),
        volatility_percentile=_optional(last["volatility_percentile"]),
        regime=_regime(last["regime"]),
        raw_regime=_regime(last["raw_regime"]),
        corr_btc_90=None if is_benchmark else _optional(last["corr_btc_90"]),
        corr_percentile=corr_percentile,
        corr_level=_correlation_level(corr_percentile, regime_config),
        typical_daily_move=float(daily_moves.median()) if not daily_moves.empty else None,
        big_daily_move=float(daily_moves.quantile(0.9)) if not daily_moves.empty else None,
        support_30=range_30[0] if range_30 else None,
        resistance_30=range_30[1] if range_30 else None,
        support_90=range_90[0] if range_90 else None,
        resistance_90=range_90[1] if range_90 else None,
    )


def _optional(value: Any) -> float | None:
    """NaN/NULL do pandas -> None."""
    return None if pd.isna(value) else float(value)


def _regime(value: Any) -> Regime | None:
    return None if pd.isna(value) else Regime(str(value))


def _change(close: pd.Series, days: int) -> float | None:
    if len(close) <= days:
        return None
    return float(close.iloc[-1] / close.iloc[-1 - days] - 1)


def _correlation_level(percentile: float | None, config: RegimeConfig) -> CorrelationLevel | None:
    # Mesmos cortes dos regimes (33/66): o "normal" da correlação é o terço do meio do histórico.
    if percentile is None:
        return None
    if percentile <= config.calm_below:
        return CorrelationLevel.BELOW_USUAL
    if percentile > config.high_above:
        return CorrelationLevel.ABOVE_USUAL
    return CorrelationLevel.USUAL
