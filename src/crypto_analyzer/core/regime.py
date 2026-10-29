"""Regime de volatilidade (calma / normal / alta) pelo percentil do histórico do próprio ativo.

Cada data usa só dados até ela mesma: nenhum valor futuro entra no rótulo daquele dia.
"""

import numpy as np
import pandas as pd

from crypto_analyzer.core.indicators import log_returns
from crypto_analyzer.core.models import Regime


def realized_volatility(close: pd.Series, window: int = 30) -> pd.Series:
    """Volatilidade realizada: desvio padrão dos retornos diários nos últimos `window` dias."""
    volatility: pd.Series = log_returns(close).rolling(window, min_periods=window).std()
    return volatility.rename("volatility")


def volatility_percentile(volatility: pd.Series, window: int, min_history: int) -> pd.Series:
    """Posição (0 a 100) da volatilidade de cada dia entre os últimos `window` valores.

    100 = a mais alta da janela. Janela móvel e não histórico inteiro: a volatilidade das
    criptos caiu com a maturidade do mercado, e com o histórico inteiro os dias de hoje
    pareceriam quase sempre "calmos" (medido nos dados reais). Abaixo de `min_history`
    valores, o resultado é NaN: sem histórico suficiente não há conclusão confiável.
    """
    ranked: pd.Series = volatility.rolling(window, min_periods=min_history).rank(pct=True)
    return (ranked * 100).rename("volatility_percentile")


def classify(percentile: pd.Series, calm_below: float, high_above: float) -> pd.Series:
    """Percentil -> regime. `<= calm_below` é calma, `> high_above` é alta, o resto é normal."""
    labels = np.select(
        [percentile <= calm_below, percentile > high_above],
        [Regime.CALM.value, Regime.HIGH.value],
        default=Regime.NORMAL.value,
    )
    result = pd.Series(labels, index=percentile.index, dtype="string")
    return result.mask(percentile.isna()).rename("raw_regime")


def apply_hysteresis(raw: pd.Series, confirm_days: int) -> pd.Series:
    """Só troca de regime depois de `confirm_days` dias seguidos no regime novo.

    Evita que o regime "pisque" quando o percentil fica na fronteira entre dois rótulos.
    É uma máquina de estados (o resultado de hoje depende do de ontem), por isso usa um
    laço em vez de uma operação vetorizada.
    """
    if confirm_days < 1:
        raise ValueError("confirm_days deve ser pelo menos 1")

    output: list[str | None] = []
    current: str | None = None
    candidate: str | None = None
    streak = 0
    for value in raw.astype(object).where(raw.notna(), None):
        if value is None:
            output.append(None)
            continue
        if current is None or value == current:
            current, candidate, streak = value, None, 0
        else:
            streak = streak + 1 if value == candidate else 1
            candidate = value
            if streak >= confirm_days:
                current, candidate, streak = value, None, 0
        output.append(current)
    return pd.Series(output, index=raw.index, dtype="string", name="regime")


def compute_regimes(
    close: pd.Series,
    *,
    volatility_window: int,
    percentile_window: int,
    min_history: int,
    calm_below: float,
    high_above: float,
    confirm_days: int,
) -> pd.DataFrame:
    """Preços de fechamento -> volatilidade, percentil, regime "cru" e regime com histerese."""
    volatility = realized_volatility(close, volatility_window)
    percentile = volatility_percentile(volatility, percentile_window, min_history)
    raw = classify(percentile, calm_below, high_above)
    return pd.DataFrame(
        {
            "volatility": volatility,
            "percentile": percentile,
            "raw_regime": raw,
            "regime": apply_hysteresis(raw, confirm_days),
        }
    )
