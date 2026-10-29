import numpy as np
import pandas as pd
import pytest

from crypto_analyzer.config import RegimeConfig
from crypto_analyzer.core.indicators import rsi
from crypto_analyzer.pipeline.gold import (
    INDICATOR_COLUMNS,
    REGIME_COLUMNS,
    compute_gold,
    compute_indicators,
)

REGIME = RegimeConfig(
    volatility_window=10,
    percentile_window=100,
    min_history=40,
    calm_below=33,
    high_above=66,
    confirm_days=3,
)


def make_candles(days: int, start: str, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    index = pd.date_range(start, periods=days, freq="D", tz="UTC", name="ts")
    close = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.02, days))), index=index)
    return pd.DataFrame(
        {"high": close * 1.01, "low": close * 0.99, "close": close, "open": close, "volume": 1.0}
    )


@pytest.fixture
def candles() -> dict[str, pd.DataFrame]:
    # a SOL começa 100 dias depois do BTC, como na vida real (histórico mais curto)
    return {
        "BTC-BRL": make_candles(400, "2025-01-01", seed=1),
        "SOL-BRL": make_candles(300, "2025-04-11", seed=2),
    }


def test_indicator_frame_has_exactly_the_table_columns(candles: dict[str, pd.DataFrame]) -> None:
    frame = compute_indicators(candles["BTC-BRL"], None)

    assert list(frame.columns) == INDICATOR_COLUMNS
    assert frame.index.equals(candles["BTC-BRL"].index)


def test_indicator_values_come_from_the_core_functions(candles: dict[str, pd.DataFrame]) -> None:
    btc = candles["BTC-BRL"]

    frame = compute_indicators(btc, None)

    pd.testing.assert_series_equal(frame["rsi_14"], rsi(btc["close"], 14), check_names=False)
    assert frame["sma_200"].isna().sum() == 199  # aquecimento: sem número inventado


def test_benchmark_has_no_correlation_with_itself_but_others_do(
    candles: dict[str, pd.DataFrame],
) -> None:
    gold = compute_gold(candles, "BTC-BRL", REGIME)

    assert gold["BTC-BRL"].indicators["corr_btc_90"].isna().all()
    sol = gold["SOL-BRL"].indicators["corr_btc_90"]
    assert sol.notna().sum() == 300 - 90  # retornos: 299; janela de 90 -> 299 - 89 = 210
    assert sol.dropna().between(-1, 1).all()


def test_gold_frames_are_aligned_with_their_candles(candles: dict[str, pd.DataFrame]) -> None:
    gold = compute_gold(candles, "BTC-BRL", REGIME)

    for symbol, frames in gold.items():
        assert frames.indicators.index.equals(candles[symbol].index)
        assert frames.regimes.index.equals(candles[symbol].index)
        assert list(frames.regimes.columns) == REGIME_COLUMNS
