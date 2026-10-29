import numpy as np
import pandas as pd
import pandas_ta_classic as ta
import pytest

from crypto_analyzer.core.indicators import (
    atr,
    bollinger,
    ema,
    log_returns,
    macd,
    rolling_correlation,
    rsi,
    sma,
    true_range,
)


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


# --- MACD e ATR ---


@pytest.fixture
def ohlc(close: pd.Series) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    return pd.DataFrame(
        {
            "high": close * (1 + rng.uniform(0, 0.02, len(close))),
            "low": close * (1 - rng.uniform(0, 0.02, len(close))),
            "close": close,
        }
    )


@pytest.mark.parametrize(("fast", "slow", "signal"), [(12, 26, 9), (5, 35, 5), (8, 17, 9)])
def test_macd_matches_reference(close: pd.Series, fast: int, slow: int, signal: int) -> None:
    mine = macd(close, fast, slow, signal)
    reference = ta.macd(close, fast=fast, slow=slow, signal=signal)

    assert_matches_reference(mine["macd"], reference[f"MACD_{fast}_{slow}_{signal}"])
    assert_matches_reference(mine["signal"], reference[f"MACDs_{fast}_{slow}_{signal}"])
    assert_matches_reference(mine["histogram"], reference[f"MACDh_{fast}_{slow}_{signal}"])


@pytest.mark.parametrize("window", [7, 14, 21])
def test_atr_matches_reference(ohlc: pd.DataFrame, window: int) -> None:
    mine = atr(ohlc["high"], ohlc["low"], ohlc["close"], window)
    reference = ta.atr(ohlc["high"], ohlc["low"], ohlc["close"], length=window)

    assert_matches_reference(mine, reference)


def test_true_range_by_hand_includes_the_gap() -> None:
    high = pd.Series([10.0, 11.0, 14.0, 13.0])
    low = pd.Series([8.0, 9.0, 12.0, 11.0])
    close = pd.Series([9.0, 10.0, 13.0, 12.0])

    result = true_range(high, low, close)

    # candle 2 abriu com gap de alta: |14 - 10| = 4 é maior que 14 - 12 = 2
    assert result.isna().tolist() == [True, False, False, False]
    assert result.dropna().tolist() == [2.0, 4.0, 2.0]


def test_atr_by_hand() -> None:
    high = pd.Series([10.0, 11.0, 14.0, 13.0])
    low = pd.Series([8.0, 9.0, 12.0, 11.0])
    close = pd.Series([9.0, 10.0, 13.0, 12.0])

    result = atr(high, low, close, window=2)

    # true range = [NaN, 2, 4, 2]; semente = média(2, 4) = 3; depois 0.5*2 + 0.5*3 = 2.5
    assert result.dropna().tolist() == [3.0, 2.5]


def test_macd_histogram_is_macd_minus_signal_and_warmup_is_right(close: pd.Series) -> None:
    result = macd(close)

    pd.testing.assert_series_equal(
        result["histogram"], result["macd"] - result["signal"], check_names=False
    )
    assert result["macd"].isna().sum() == 25  # precisa de 26 preços para a EMA lenta
    assert result["signal"].isna().sum() == 33  # + 8 valores para a semente do sinal


def test_macd_is_zero_for_constant_price_and_positive_in_an_uptrend() -> None:
    assert macd(pd.Series([50.0] * 60)).dropna().eq(0.0).to_numpy().all()

    uptrend = macd(pd.Series(np.arange(1.0, 100.0)))
    assert (uptrend["macd"].dropna() > 0).all()


def test_atr_is_never_negative_and_zero_when_nothing_moves(ohlc: pd.DataFrame) -> None:
    assert (atr(ohlc["high"], ohlc["low"], ohlc["close"]).dropna() >= 0).all()

    flat = pd.Series([5.0] * 30)
    assert atr(flat, flat, flat).dropna().eq(0.0).all()


def test_macd_and_atr_only_use_past_values(ohlc: pd.DataFrame) -> None:
    altered = ohlc.copy()
    altered.iloc[200:] = altered.iloc[200:] * 2

    pd.testing.assert_frame_equal(macd(ohlc["close"]).iloc[:200], macd(altered["close"]).iloc[:200])
    pd.testing.assert_series_equal(
        atr(ohlc["high"], ohlc["low"], ohlc["close"]).iloc[:200],
        atr(altered["high"], altered["low"], altered["close"]).iloc[:200],
    )


def test_macd_rejects_fast_not_smaller_than_slow(close: pd.Series) -> None:
    with pytest.raises(ValueError, match="fast"):
        macd(close, fast=26, slow=12)


# --- Bollinger e correlação ---


@pytest.mark.parametrize(("window", "num_std"), [(20, 2.0), (10, 1.5), (50, 3.0)])
def test_bollinger_matches_reference(close: pd.Series, window: int, num_std: float) -> None:
    mine = bollinger(close, window, num_std)
    reference = ta.bbands(close, length=window, std=num_std)

    assert_matches_reference(mine["lower"], reference[f"BBL_{window}_{num_std}"])
    assert_matches_reference(mine["middle"], reference[f"BBM_{window}_{num_std}"])
    assert_matches_reference(mine["upper"], reference[f"BBU_{window}_{num_std}"])


def test_bollinger_by_hand_uses_population_deviation() -> None:
    # janela [1, 2, 3]: média 2; desvio populacional = sqrt(2/3); (o amostral seria 1.0)
    result = bollinger(pd.Series([1.0, 2.0, 3.0]), window=3, num_std=2.0)

    assert result["middle"].iloc[2] == pytest.approx(2.0)
    assert result["upper"].iloc[2] == pytest.approx(2.0 + 2 * np.sqrt(2 / 3))
    assert result["lower"].iloc[2] == pytest.approx(2.0 - 2 * np.sqrt(2 / 3))


def test_bollinger_bands_are_ordered_and_collapse_when_price_is_constant(
    close: pd.Series,
) -> None:
    bands = bollinger(close).dropna()
    assert (bands["lower"] <= bands["middle"]).all()
    assert (bands["middle"] <= bands["upper"]).all()

    flat = bollinger(pd.Series([7.0] * 30)).dropna()
    assert (flat["upper"] == flat["lower"]).all()


def test_log_returns_by_hand() -> None:
    result = log_returns(pd.Series([100.0, 110.0, 99.0]))

    assert np.isnan(result.iloc[0])
    assert result.iloc[1] == pytest.approx(np.log(1.1))
    assert result.iloc[2] == pytest.approx(np.log(0.9))


def test_rolling_correlation_matches_numpy_on_every_window(close: pd.Series) -> None:
    rng = np.random.default_rng(1)
    a = log_returns(close).dropna()
    b = a * 0.5 + pd.Series(rng.normal(0, 0.02, len(a)), index=a.index)

    result = rolling_correlation(a, b, window=30)

    expected = [
        np.corrcoef(a.iloc[i - 29 : i + 1], b.iloc[i - 29 : i + 1])[0, 1] for i in range(29, len(a))
    ]
    assert result.isna().sum() == 29
    assert result.dropna().to_numpy() == pytest.approx(expected, abs=1e-9)


def test_correlation_is_plus_one_for_same_moves_and_minus_one_for_opposite(
    close: pd.Series,
) -> None:
    r = log_returns(close).dropna()

    assert rolling_correlation(r, r * 3, 20).dropna().to_numpy() == pytest.approx(1.0)
    assert rolling_correlation(r, -r, 20).dropna().to_numpy() == pytest.approx(-1.0)


def test_correlation_only_counts_dates_both_series_have() -> None:
    index = pd.date_range("2026-01-01", periods=60, freq="D", tz="UTC")
    rng = np.random.default_rng(3)
    btc = pd.Series(rng.normal(0, 0.02, 60), index=index)
    sol = btc.iloc[30:] * 2  # começou 30 dias depois

    result = rolling_correlation(sol, btc, window=10)

    assert result.index[0] == index[30]  # só existe onde as duas têm dado
    assert result.isna().sum() == 9
    assert result.dropna().to_numpy() == pytest.approx(1.0)


def test_bollinger_and_correlation_only_use_past_values(close: pd.Series) -> None:
    altered = close.copy()
    altered.iloc[200:] = altered.iloc[200:] * 2
    other = close.shift(1).bfill() * 1.01

    pd.testing.assert_frame_equal(bollinger(close).iloc[:200], bollinger(altered).iloc[:200])
    pd.testing.assert_series_equal(
        rolling_correlation(log_returns(close), log_returns(other), 30).iloc[:200],
        rolling_correlation(log_returns(altered), log_returns(other), 30).iloc[:200],
    )


def test_correlation_needs_a_window_of_at_least_two() -> None:
    with pytest.raises(ValueError, match="window"):
        rolling_correlation(pd.Series([1.0, 2.0]), pd.Series([1.0, 2.0]), window=1)
