import numpy as np
import pandas as pd
import pytest

from crypto_analyzer.config import load_backtest_config
from crypto_analyzer.core.backtest import (
    evaluate,
    forward_returns,
    independent_events,
    run_backtest,
    signal_events,
)
from crypto_analyzer.core.models import Signal


def daily(values: list[float], start: str = "2026-01-01") -> pd.Series:
    index = pd.date_range(start, periods=len(values), freq="D", tz="UTC")
    return pd.Series(values, index=index, dtype="float64")


def flags(days: list[int], length: int = 40) -> pd.Series:
    values = np.zeros(length, dtype=bool)
    values[days] = True
    index = pd.date_range("2026-01-01", periods=length, freq="D", tz="UTC")
    return pd.Series(values, index=index)


# --- sinais ---


def test_rsi_signal_is_the_crossing_day_only() -> None:
    rsi = daily([65, 71, 75, 69, 72, 25, 35, 29])
    close = daily([1.0] * 8)
    sma = daily([np.nan] * 8)

    events = signal_events(close, rsi, sma)

    # cruza 70 no dia 1 e de novo no dia 4; os dias 2 (ainda acima) não contam
    assert events[Signal.RSI_ABOVE_HIGH].tolist() == [0, 1, 0, 0, 1, 0, 0, 0]
    # cai abaixo de 30 no dia 5 e de novo no dia 7
    assert events[Signal.RSI_BELOW_LOW].tolist() == [0, 0, 0, 0, 0, 1, 0, 1]


def test_sma_crossings_need_the_average_on_both_days() -> None:
    close = daily([90, 110, 120, 95, 105])
    sma = daily([np.nan, 100, 100, 100, 100])

    events = signal_events(close, daily([50.0] * 5), sma)

    # dia 1: acima, mas ontem não havia média -> não é cruzamento
    assert events[Signal.CROSS_ABOVE_SMA_200].tolist() == [0, 0, 0, 0, 1]
    assert events[Signal.CROSS_BELOW_SMA_200].tolist() == [0, 0, 0, 1, 0]


def test_unknown_rsi_is_never_a_signal() -> None:
    rsi = daily([np.nan, 80, np.nan, 20])

    events = signal_events(daily([1.0] * 4), rsi, daily([np.nan] * 4))

    assert not events[Signal.RSI_ABOVE_HIGH].any()
    assert not events[Signal.RSI_BELOW_LOW].any()


# --- retornos ---


def test_forward_return_by_hand() -> None:
    close = daily([100, 110, 121, 100])

    assert forward_returns(close, 2).tolist()[:2] == pytest.approx([0.21, 100 / 110 - 1])
    assert forward_returns(close, 2).iloc[2:].isna().all()  # o futuro ainda não aconteceu


def test_forward_return_uses_calendar_days_and_leaves_gaps_empty() -> None:
    """Sem o candle do dia 3, o retorno de 2 dias do dia 1 fica vazio (não usa o dia 4)."""
    index = pd.DatetimeIndex(["2026-01-01", "2026-01-02", "2026-01-04", "2026-01-05"], tz="UTC")
    close = pd.Series([100.0, 110.0, 130.0, 140.0], index=index)

    returns = forward_returns(close, 2)

    assert np.isnan(returns.iloc[0])  # 01/01 + 2 dias = 03/01, que não existe
    assert returns.iloc[1] == pytest.approx(130 / 110 - 1)  # 02/01 + 2 dias = 04/01
    assert returns.iloc[2:].isna().all()  # 06/01 e 07/01 ainda não aconteceram


# --- independência ---


def test_signals_inside_the_horizon_are_grouped() -> None:
    events = flags([0, 3, 6, 7, 20, 26])

    kept = independent_events(events, horizon_days=7)

    # 0 conta; 3 e 6 caem dentro dos 7 dias; 7 conta; 20 conta; 26 (a 6 dias) não
    assert list(np.flatnonzero(kept.to_numpy())) == [0, 7, 20]


# --- avaliação ---


def test_small_sample_reports_counts_but_no_average() -> None:
    close = daily(list(np.linspace(100, 140, 40)))
    events = flags([0, 10])

    result = evaluate(events, close, Signal.RSI_ABOVE_HIGH, horizon_days=7, min_sample=3)

    assert (result.raw_count, result.independent_count, result.evaluated_count) == (2, 2, 2)
    assert not result.enough_sample
    assert result.mean_return is None and result.hit_rate is None
    assert result.baseline_mean is not None  # a linha de base aparece mesmo assim


def test_enough_sample_by_hand() -> None:
    # preço sobe 10% em 7 dias a partir dos dias 0 e 7; cai 10% a partir do dia 14
    values = [100.0] * 30
    values[7], values[14], values[21] = 110.0, 121.0, 108.9
    close = daily(values)
    events = flags([0, 7, 14], length=30)

    result = evaluate(events, close, Signal.RSI_ABOVE_HIGH, horizon_days=7, min_sample=3)

    assert result.enough_sample
    assert result.mean_return == pytest.approx((0.10 + 0.10 - 0.10) / 3)
    assert result.median_return == pytest.approx(0.10)
    assert result.hit_rate == pytest.approx(2 / 3)


def test_events_without_a_future_price_are_not_evaluated() -> None:
    close = daily([100.0] * 10)
    events = flags([1, 8], length=10)  # o dia 8 + 7 dias não existe ainda

    result = evaluate(events, close, Signal.RSI_ABOVE_HIGH, horizon_days=7, min_sample=1)

    assert (result.independent_count, result.evaluated_count) == (2, 1)


def test_run_backtest_covers_every_signal_and_horizon() -> None:
    rng = np.random.default_rng(3)
    close = daily(list(100 * np.exp(np.cumsum(rng.normal(0, 0.03, 400)))))
    rsi = daily(list(rng.uniform(20, 80, 400)))
    sma = close.rolling(200).mean()

    results = run_backtest(close, rsi, sma, horizons_days=[7, 30], min_sample=20)

    assert [(r.signal, r.horizon_days) for r in results] == [
        (signal, horizon) for signal in Signal for horizon in (7, 30)
    ]
    for r in results:
        assert r.raw_count >= r.independent_count >= r.evaluated_count
        assert r.enough_sample == (r.evaluated_count >= 20)


def test_backtest_yaml_has_the_authors_decisions() -> None:
    config = load_backtest_config()

    assert config.min_sample == 20
    assert config.horizons_days == [7, 30]
