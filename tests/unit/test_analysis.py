from datetime import UTC, datetime

import numpy as np
import pandas as pd
import pytest

from crypto_analyzer.config import RegimeConfig
from crypto_analyzer.core.models import CorrelationLevel, Regime, Trend
from crypto_analyzer.pipeline.analysis import assemble_analysis
from crypto_analyzer.pipeline.gold import compute_gold

REGIME = RegimeConfig(
    volatility_window=10,
    percentile_window=100,
    min_history=40,
    calm_below=33,
    high_above=66,
    confirm_days=3,
)
NOW = datetime(2026, 10, 29, 12, tzinfo=UTC)
DAYS = 500


def make_candles(seed: int, drift: float, days: int = DAYS) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    index = pd.date_range("2025-06-01", periods=days, freq="D", tz="UTC", name="ts")
    close = pd.Series(100 * np.exp(np.cumsum(rng.normal(drift, 0.02, days))), index=index)
    return pd.DataFrame(
        {"open": close, "high": close * 1.01, "low": close * 0.99, "close": close, "volume": 1.0}
    )


def frame_for(symbol: str, candles: dict[str, pd.DataFrame]) -> pd.DataFrame:
    gold = compute_gold(candles, "BTC-BRL", REGIME)[symbol]
    return pd.concat(
        [candles[symbol][["high", "low", "close"]], gold.indicators, gold.regimes], axis=1
    )


def build(symbol: str = "SOL-BRL", **overrides: object):  # noqa: ANN202
    candles = {"BTC-BRL": make_candles(1, 0.001), "SOL-BRL": make_candles(2, 0.004)}
    last_ts = candles[symbol].index[-1].to_pydatetime() + pd.Timedelta(days=1)
    kwargs: dict[str, object] = {
        "symbol": symbol,
        "base": symbol.split("-")[0],
        "name": "Teste",
        "article": "a",
        "is_benchmark": symbol == "BTC-BRL",
        "frame": frame_for(symbol, candles),
        "last_candle_ts": last_ts,
        "now": NOW,
        "max_age_hours": 48.0,
        "regime_config": REGIME,
    }
    kwargs.update(overrides)
    return assemble_analysis(**kwargs), candles  # type: ignore[arg-type]


def test_price_and_changes_come_from_the_closes() -> None:
    analysis, candles = build()
    close = candles["SOL-BRL"]["close"]

    assert analysis.price == pytest.approx(close.iloc[-1])
    assert analysis.change_1d == pytest.approx(close.iloc[-1] / close.iloc[-2] - 1)
    assert analysis.change_7d == pytest.approx(close.iloc[-1] / close.iloc[-8] - 1)
    assert analysis.change_30d == pytest.approx(close.iloc[-1] / close.iloc[-31] - 1)
    assert analysis.as_of == close.index[-1].to_pydatetime()


def test_a_steady_climb_is_read_as_an_uptrend_with_indicators_filled() -> None:
    analysis, _ = build()

    assert analysis.trend is Trend.UP
    assert analysis.regime in set(Regime)
    assert analysis.sma_200 is not None and analysis.rsi_14 is not None
    assert analysis.support_90 is not None and analysis.resistance_90 is not None
    assert analysis.support_90 <= analysis.price <= analysis.resistance_90


def test_typical_moves_are_ordered_and_positive() -> None:
    analysis, _ = build()

    assert analysis.typical_daily_move is not None and analysis.big_daily_move is not None
    assert 0 < analysis.typical_daily_move < analysis.big_daily_move


def test_correlation_is_filled_for_others_and_absent_for_the_benchmark() -> None:
    sol, _ = build("SOL-BRL")
    btc, _ = build("BTC-BRL")

    assert sol.corr_btc_90 is not None and -1 <= sol.corr_btc_90 <= 1
    assert sol.corr_percentile is not None
    assert sol.corr_level in set(CorrelationLevel)
    assert btc.corr_btc_90 is None and btc.corr_level is None and btc.is_benchmark


def test_short_history_gives_none_instead_of_numbers() -> None:
    candles = {"BTC-BRL": make_candles(1, 0.001, 60), "SOL-BRL": make_candles(2, 0.004, 60)}
    frame = frame_for("SOL-BRL", candles)

    analysis = assemble_analysis(
        symbol="SOL-BRL",
        base="SOL",
        name="Solana",
        article="a",
        is_benchmark=False,
        frame=frame,
        last_candle_ts=frame.index[-1].to_pydatetime(),
        now=NOW,
        max_age_hours=48.0,
        regime_config=REGIME,
    )

    assert analysis.trend is None and analysis.sma_200 is None  # só 60 dias
    assert analysis.support_90 is None and analysis.change_30d is not None


def test_stale_data_is_flagged_by_the_age_limit() -> None:
    fresh, _ = build(last_candle_ts=NOW - pd.Timedelta(hours=20))
    old, _ = build(last_candle_ts=NOW - pd.Timedelta(days=5))

    assert not fresh.is_stale and fresh.data_age_hours == pytest.approx(20.0)
    assert old.is_stale and old.data_age_hours == pytest.approx(120.0)


def test_empty_frame_is_rejected() -> None:
    with pytest.raises(ValueError, match="sem dados"):
        assemble_analysis(
            symbol="SOL-BRL",
            base="SOL",
            name="Solana",
            article="a",
            is_benchmark=False,
            frame=pd.DataFrame(),
            last_candle_ts=NOW,
            now=NOW,
            max_age_hours=48.0,
            regime_config=REGIME,
        )
