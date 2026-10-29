import numpy as np
import pandas as pd
import pandas_ta_classic as ta
import pytest

from crypto_analyzer.core.indicators import ema, rsi, sma


@pytest.fixture
def close() -> pd.Series:
    """Passeio aleatório com semente fixa: sempre os mesmos 300 preços."""
    rng = np.random.default_rng(42)
    prices = 100 * np.exp(np.cumsum(rng.normal(0, 0.02, 300)))
    index = pd.date_range("2026-01-01", periods=300, freq="D", tz="UTC", name="ts")
    return pd.Series(prices, index=index, name="close")


def assert_matches_reference(mine: pd.Series, reference: pd.Series) -> None:
    pd.testing.assert_series_equal(mine, reference, check_names=False, rtol=1e-9, atol=1e-9)


# --- validação contra o gabarito (pandas-ta-classic, só nos testes) ---


@pytest.mark.parametrize("window", [5, 20, 50, 200])
def test_sma_matches_reference(close: pd.Series, window: int) -> None:
    assert_matches_reference(sma(close, window), ta.sma(close, length=window))


@pytest.mark.parametrize("window", [12, 20, 26, 50])
def test_ema_matches_reference(close: pd.Series, window: int) -> None:
    assert_matches_reference(ema(close, window), ta.ema(close, length=window))


@pytest.mark.parametrize("window", [7, 14, 21])
def test_rsi_matches_reference(close: pd.Series, window: int) -> None:
    assert_matches_reference(rsi(close, window), ta.rsi(close, length=window))


# --- valores calculados à mão ---


def test_sma_by_hand() -> None:
    result = sma(pd.Series([1.0, 2.0, 3.0, 4.0, 5.0]), 3)

    assert result.isna().tolist() == [True, True, False, False, False]
    assert result.dropna().tolist() == [2.0, 3.0, 4.0]


def test_ema_by_hand() -> None:
    # window=3 -> alpha=0.5. Semente = SMA(1,2,3) = 2.0; depois 0.5*4 + 0.5*2 = 3.0
    result = ema(pd.Series([1.0, 2.0, 3.0, 4.0, 5.0]), 3)

    assert result.dropna().tolist() == [2.0, 3.0, 4.0]


def test_rsi_by_hand() -> None:
    # window=2: variações [+2, -1, +3]. Médias iniciais (2 primeiras): ganho 1.0, perda 0.5.
    # Wilder (alpha 1/2): ganho = 0.5*3 + 0.5*1.0 = 2.0; perda = 0.5*0 + 0.5*0.5 = 0.25
    result = rsi(pd.Series([10.0, 12.0, 11.0, 14.0]), window=2)

    assert result.iloc[2] == pytest.approx(100 - 100 / (1 + 1.0 / 0.5))
    assert result.iloc[3] == pytest.approx(100 - 100 / (1 + 2.0 / 0.25))


# --- propriedades e bordas ---


def test_first_window_minus_one_values_are_nan(close: pd.Series) -> None:
    assert sma(close, 20).isna().sum() == 19
    assert ema(close, 20).isna().sum() == 19
    assert rsi(close, 14).isna().sum() == 14  # a 1ª variação só existe a partir do 2º preço


def test_rsi_is_always_between_0_and_100(close: pd.Series) -> None:
    result = rsi(close).dropna()

    assert result.between(0, 100).all()


def test_rsi_is_100_when_price_only_rises_and_0_when_only_falls() -> None:
    rising = pd.Series(np.arange(1.0, 40.0))

    assert rsi(rising).dropna().eq(100.0).all()
    assert rsi(-rising + 100).dropna().eq(0.0).all()


def test_rsi_is_nan_when_price_never_changes() -> None:
    assert rsi(pd.Series([5.0] * 30)).isna().all()


def test_series_shorter_than_window_is_all_nan() -> None:
    short = pd.Series([1.0, 2.0, 3.0])

    assert ema(short, 10).isna().all()
    assert rsi(short, 14).isna().all()


def test_indicators_only_use_past_values(close: pd.Series) -> None:
    """Mudar o futuro não pode alterar o que já foi calculado (sem look-ahead)."""
    altered = close.copy()
    altered.iloc[200:] = altered.iloc[200:] * 2

    for indicator in (lambda s: sma(s, 20), lambda s: ema(s, 20), rsi):
        pd.testing.assert_series_equal(indicator(close).iloc[:200], indicator(altered).iloc[:200])


def test_invalid_window_is_rejected(close: pd.Series) -> None:
    with pytest.raises(ValueError, match="window"):
        sma(close, 0)
