"""Indicadores técnicos como funções puras sobre pandas Series (sem I/O).

Todos descrevem o passado: usam só valores até cada data, nunca valores futuros.
Os primeiros `window - 1` resultados são NaN (ainda não há dados suficientes).
"""

import numpy as np
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


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """MACD: diferença entre uma EMA rápida e uma lenta, mostrando a "força" da tendência.

    Colunas: `macd` (rápida - lenta), `signal` (EMA do próprio macd, mais suave) e
    `histogram` (macd - signal; positivo quando o macd está acima da sua média).
    """
    _check_window(fast)
    _check_window(signal)
    if fast >= slow:
        raise ValueError("fast deve ser menor que slow")
    macd_line = ema(close, fast) - ema(close, slow)
    signal_line = _seeded_ewm(macd_line, alpha=2 / (signal + 1), window=signal)
    return pd.DataFrame(
        {"macd": macd_line, "signal": signal_line, "histogram": macd_line - signal_line}
    )


def true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    """Maior distância percorrida no candle, contando o salto (gap) desde o fechamento anterior.

    É o maior entre: máxima - mínima, |máxima - fechamento anterior| e |mínima - fechamento
    anterior|. O primeiro candle fica NaN, pois não há fechamento anterior (mesma convenção
    da TA-Lib e do gabarito).
    """
    previous_close = close.shift(1)
    ranges = pd.concat(
        [high - low, (high - previous_close).abs(), (low - previous_close).abs()], axis=1
    )
    # skipna=False: se faltar o fechamento anterior, o resultado é NaN em vez de só high - low.
    return ranges.max(axis=1, skipna=False).rename("true_range")


def atr(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.Series:
    """ATR de Wilder: média suavizada do true range, em unidades de preço (R$).

    Diz quanto o preço costuma oscilar por candle; maior ATR = mercado mais agitado.
    """
    _check_window(window)
    return _seeded_ewm(true_range(high, low, close), alpha=1 / window, window=window).rename(
        f"atr_{window}"
    )


def bollinger(close: pd.Series, window: int = 20, num_std: float = 2.0) -> pd.DataFrame:
    """Bandas de Bollinger: uma média (`middle`) com faixas `num_std` desvios acima e abaixo.

    Preço perto da faixa de cima = esticado para cima em relação ao normal recente; o mesmo
    vale para baixo. Colunas: `lower`, `middle`, `upper`.
    """
    _check_window(window)
    middle = close.rolling(window, min_periods=window).mean()
    # ddof=0 (desvio populacional) é a convenção de Bollinger/TradingView e do gabarito.
    # O padrão do pandas é ddof=1, que daria bandas ligeiramente mais largas.
    deviation = close.rolling(window, min_periods=window).std(ddof=0)
    return pd.DataFrame(
        {
            "lower": middle - num_std * deviation,
            "middle": middle,
            "upper": middle + num_std * deviation,
        }
    )


def log_returns(close: pd.Series) -> pd.Series:
    """Retorno logarítmico de um candle para o seguinte: ln(fechamento / fechamento anterior).

    O primeiro valor é NaN. Se faltarem candles no meio, o retorno cobre mais de um passo.
    """
    returns: pd.Series = np.log(close).diff()
    return returns.rename("log_return")


def rolling_correlation(returns: pd.Series, other: pd.Series, window: int) -> pd.Series:
    """Correlação (de -1 a 1) entre dois retornos nas últimas `window` datas em comum.

    1 = andam juntos; 0 = independentes; -1 = andam em sentidos opostos. Só as datas presentes
    nas duas séries contam (ex.: a SOL começou depois do BTC), então a janela é de datas
    em comum e não de dias corridos.
    """
    if window < 2:
        raise ValueError("window deve ser pelo menos 2 para calcular correlação")
    both = pd.concat([returns, other], axis=1, join="inner")
    correlation: pd.Series = (
        both.iloc[:, 0].rolling(window, min_periods=window).corr(both.iloc[:, 1])
    )
    return correlation.rename("correlation")


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
