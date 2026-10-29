"""Indicadores técnicos como funções puras sobre pandas Series (sem I/O).

Todos descrevem o passado: usam só valores até cada data, nunca valores futuros.
Os primeiros `window - 1` resultados são NaN (ainda não há dados suficientes).
"""

import pandas as pd


def sma(close: pd.Series, window: int) -> pd.Series:
    """Média móvel simples: a média dos últimos `window` valores."""
    _check_window(window)
    return close.rolling(window, min_periods=window).mean().rename(f"sma_{window}")


def ema(close: pd.Series, window: int) -> pd.Series:
    """Média móvel exponencial: dá mais peso aos valores recentes (alpha = 2 / (window + 1))."""
    _check_window(window)
    return _seeded_ewm(close, alpha=2 / (window + 1), window=window).rename(f"ema_{window}")


def rsi(close: pd.Series, window: int = 14) -> pd.Series:
    """RSI de Wilder, de 0 a 100: compara a força das altas com a das quedas recentes.

    Acima de ~70 costuma ser lido como "subiu rápido demais"; abaixo de ~30, "caiu rápido demais".
    Sem nenhuma queda na janela dá 100; sem nenhuma variação (preço parado) fica NaN.
    """
    _check_window(window)
    change = close.diff()
    # Médias de Wilder = EMA com alpha 1/window (mais lenta que a EMA comum de mesmo window).
    avg_gain = _seeded_ewm(change.clip(lower=0), alpha=1 / window, window=window)
    avg_loss = _seeded_ewm((-change).clip(lower=0), alpha=1 / window, window=window)
    # avg_loss == 0 gera divisão por zero (inf) e o RSI vira exatamente 100, como deve ser.
    return (100 - 100 / (1 + avg_gain / avg_loss)).rename(f"rsi_{window}")


def _seeded_ewm(values: pd.Series, alpha: float, window: int) -> pd.Series:
    """Média exponencial que começa com a SMA dos primeiros `window` valores válidos.

    É a convenção clássica (Wilder, TradingView). Começar do primeiro valor daria
    resultados diferentes no começo, que só convergem aos poucos.
    Sem loops: colocamos a SMA como "semente" e o `ewm` do pandas segue a partir dela.
    """
    valid = values.dropna()
    result = pd.Series(float("nan"), index=values.index, dtype="float64")
    if len(valid) < window:
        return result

    seeded = valid.copy()
    seeded.iloc[: window - 1] = float("nan")
    seeded.iloc[window - 1] = valid.iloc[:window].mean()
    result.loc[valid.index] = seeded.ewm(alpha=alpha, adjust=False).mean()
    return result


def _check_window(window: int) -> None:
    if window < 1:
        raise ValueError("window deve ser pelo menos 1")
