import pandas as pd
import pytest

from crypto_analyzer.core.indicators import recent_extremes
from crypto_analyzer.core.models import Trend
from crypto_analyzer.core.regime import latest_percentile
from crypto_analyzer.core.trend import classify_trend


@pytest.mark.parametrize(
    ("close", "sma_50", "sma_200", "expected"),
    [
        (120.0, 110.0, 100.0, Trend.UP),
        (80.0, 90.0, 100.0, Trend.DOWN),
        (95.0, 110.0, 100.0, Trend.SIDEWAYS),  # abaixo da média 50, mas ela está acima da 200
        (120.0, 90.0, 100.0, Trend.SIDEWAYS),  # sinais misturados
        (100.0, 100.0, 100.0, Trend.SIDEWAYS),
    ],
)
def test_trend_needs_price_and_averages_aligned(
    close: float, sma_50: float, sma_200: float, expected: Trend
) -> None:
    assert classify_trend(close, sma_50, sma_200) is expected


def test_trend_is_unknown_without_the_200_day_average() -> None:
    assert classify_trend(100.0, 90.0, None) is None
    assert classify_trend(100.0, None, None) is None


def test_latest_percentile_by_hand() -> None:
    values = pd.Series([5.0, 1.0, 3.0, 2.0, 4.0])  # o último, 4, só perde para o 5

    assert latest_percentile(values, window=5, min_history=3) == pytest.approx(80.0)
    assert latest_percentile(values, window=3, min_history=3) == pytest.approx(100.0)  # [3, 2, 4]


def test_latest_percentile_ignores_nan_and_waits_for_history() -> None:
    values = pd.Series([float("nan"), 1.0, 2.0, float("nan")])

    assert latest_percentile(values, window=10, min_history=3) is None
    assert latest_percentile(values, window=10, min_history=2) == pytest.approx(100.0)


def test_recent_extremes_use_only_the_last_window() -> None:
    high = pd.Series([100.0, 10.0, 12.0, 11.0])
    low = pd.Series([1.0, 8.0, 9.0, 7.0])

    assert recent_extremes(high, low, window=3) == (7.0, 12.0)  # o pico de 100 saiu da janela
    assert recent_extremes(high, low, window=10) is None
