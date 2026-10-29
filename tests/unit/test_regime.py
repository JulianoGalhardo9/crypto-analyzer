import numpy as np
import pandas as pd
import pytest

from crypto_analyzer.config import load_regime_config
from crypto_analyzer.core.regime import (
    apply_hysteresis,
    classify,
    compute_regimes,
    realized_volatility,
    volatility_percentile,
)

PARAMS = {
    "volatility_window": 10,
    "percentile_window": 150,
    "min_history": 60,
    "calm_below": 33.0,
    "high_above": 66.0,
    "confirm_days": 3,
}


def series(values: list[float | str | None], dtype: str | None = None) -> pd.Series:
    index = pd.date_range("2026-01-01", periods=len(values), freq="D", tz="UTC")
    return pd.Series(values, index=index, dtype=dtype)


def block_prices() -> pd.Series:
    """200 dias calmos, 40 muito agitados, 200 calmos de novo (semente fixa)."""
    rng = np.random.default_rng(5)
    scales = [0.004] * 200 + [0.06] * 40 + [0.004] * 200
    prices = 100 * np.exp(np.cumsum(rng.normal(0, scales)))
    return series(list(prices))


# --- volatilidade realizada ---


def test_realized_volatility_is_zero_for_constant_price_and_nan_during_warmup() -> None:
    result = realized_volatility(series([10.0] * 20), window=5)

    assert result.isna().sum() == 5  # 1 retorno perdido no diff + 4 da janela
    assert result.dropna().eq(0.0).all()


def test_realized_volatility_matches_the_manual_standard_deviation() -> None:
    close = series([100.0, 102.0, 99.0, 103.0, 101.0, 105.0])

    result = realized_volatility(close, window=4)

    returns = np.log(close).diff().dropna()
    assert result.iloc[-1] == pytest.approx(returns.iloc[-4:].std())  # desvio amostral


# --- percentil ---


def test_percentile_by_hand() -> None:
    # janela 3: no índice 2 a janela é [1,2,3] e o valor 3 é o maior -> 100.
    # no índice 3 a janela é [2,3,1] e o valor 1 é o menor -> 1/3 -> 33.33...
    result = volatility_percentile(series([1.0, 2.0, 3.0, 1.0]), window=3, min_history=3)

    assert result.isna().tolist() == [True, True, False, False]
    assert result.iloc[2] == pytest.approx(100.0)
    assert result.iloc[3] == pytest.approx(100 / 3)


def test_percentile_waits_for_min_history() -> None:
    result = volatility_percentile(series(list(np.arange(1.0, 51.0))), window=40, min_history=25)

    assert result.isna().sum() == 24


def test_percentile_only_uses_the_past() -> None:
    values = np.random.default_rng(2).normal(size=200).cumsum()
    original = series(list(values))
    altered = original.copy()
    altered.iloc[120:] = altered.iloc[120:] * 10

    pd.testing.assert_series_equal(
        volatility_percentile(original, 50, 20).iloc[:120],
        volatility_percentile(altered, 50, 20).iloc[:120],
    )


# --- classificação ---


def test_classify_boundaries() -> None:
    result = classify(series([10.0, 33.0, 33.1, 66.0, 66.1, 100.0, np.nan]), 33.0, 66.0)

    assert result.iloc[:6].tolist() == ["calm", "calm", "normal", "normal", "high", "high"]
    assert pd.isna(result.iloc[6])


# --- histerese ---


def test_hysteresis_needs_consecutive_days_in_the_new_regime() -> None:
    raw = series(["a", "a", "b", "a", "b", "b", "b", "b", "b"], dtype="string")

    result = apply_hysteresis(raw, confirm_days=3)

    # o "b" solto do índice 2 é descartado; a troca só vale no 3º "b" seguido (índice 6)
    assert result.tolist() == ["a", "a", "a", "a", "a", "a", "b", "b", "b"]


def test_hysteresis_restarts_the_count_when_the_candidate_changes() -> None:
    raw = series(["a", "a", "b", "b", "c", "c", "c"], dtype="string")

    assert apply_hysteresis(raw, confirm_days=3).tolist() == ["a", "a", "a", "a", "a", "a", "c"]


def test_hysteresis_with_one_day_returns_the_raw_regime_and_keeps_leading_gaps() -> None:
    raw = series([None, None, "a", "b", "a"], dtype="string")

    result = apply_hysteresis(raw, confirm_days=1)

    assert result.isna().tolist() == [True, True, False, False, False]
    assert result.dropna().tolist() == ["a", "b", "a"]


def test_hysteresis_rejects_zero_days() -> None:
    with pytest.raises(ValueError, match="confirm_days"):
        apply_hysteresis(series(["a"], dtype="string"), confirm_days=0)


# --- junto ---


def test_a_burst_of_agitation_is_labelled_high_once_it_fills_the_volatility_window() -> None:
    result = compute_regimes(block_prices(), **PARAMS)

    assert result["regime"].iloc[:60].isna().all()  # sem histórico suficiente: sem rótulo
    # o surto começa no dia 200; a janela de volatilidade (10 dias) leva um tempo para enchê-lo
    # todo valor agitado supera todo valor calmo (110 de 150 na janela), então fica acima de ~73%
    assert result["percentile"].iloc[212:240].gt(72).all()
    assert result["regime"].iloc[220:240].eq("high").all()


def test_labels_are_relative_so_a_stable_market_still_spreads_across_labels() -> None:
    # Por design: "calma" quer dizer calma EM RELAÇÃO ao próprio histórico. Num período
    # igualmente estável, sempre haverá dias relativamente mais e menos agitados.
    result = compute_regimes(block_prices(), **PARAMS)

    assert set(result["raw_regime"].iloc[60:200].dropna()) == {"calm", "normal", "high"}


def test_hysteresis_reduces_the_number_of_regime_changes() -> None:
    result = compute_regimes(block_prices(), **PARAMS)

    def changes(labels: pd.Series) -> int:
        valid = labels.dropna()
        return int((valid != valid.shift()).sum()) - 1

    assert changes(result["regime"]) <= changes(result["raw_regime"])


def test_compute_regimes_only_uses_the_past() -> None:
    prices = block_prices()
    altered = prices.copy()
    altered.iloc[300:] = altered.iloc[300:] * 5  # só o futuro (dia 300 em diante)

    left = compute_regimes(prices, **PARAMS).iloc[:300]
    right = compute_regimes(altered, **PARAMS).iloc[:300]
    pd.testing.assert_frame_equal(left, right)


def test_regimes_yaml_loads_with_sane_values() -> None:
    config = load_regime_config()

    assert 0 < config.calm_below < config.high_above < 100
    assert config.min_history <= config.percentile_window
    assert config.confirm_days >= 1
