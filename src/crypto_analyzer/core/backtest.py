"""Backtest simples: o que aconteceu com o preço depois de cada sinal, no passado.

Descreve o passado, não prevê nada. Regras de honestidade (CLAUDE.md):
- sinais seguidos se sobrepõem; conta-se ocorrências independentes (um sinal novo só depois de
  terminar o horizonte do anterior) e reporta-se também o total bruto;
- abaixo da amostra mínima não há média, só o aviso de amostra pequena;
- todo resultado vem ao lado da linha de base (o retorno de qualquer dia no mesmo horizonte).
"""

from collections.abc import Sequence

import pandas as pd

from crypto_analyzer.core.indicators import RSI_HIGH, RSI_LOW
from crypto_analyzer.core.models import BacktestResult, Signal


def signal_events(close: pd.Series, rsi: pd.Series, sma_200: pd.Series) -> dict[Signal, pd.Series]:
    """Dias em que cada sinal acontece (o dia do cruzamento, não os dias seguintes).

    Um cruzamento exige o valor de ontem e o de hoje; dias sem indicador nunca são sinal.
    """
    rsi_known = rsi.notna() & rsi.shift(1).notna()
    above = close > sma_200
    sma_known = sma_200.notna() & sma_200.shift(1).notna()
    was_above = above.shift(1, fill_value=False).astype(bool)
    return {
        Signal.RSI_ABOVE_HIGH: rsi_known & (rsi > RSI_HIGH) & (rsi.shift(1) <= RSI_HIGH),
        Signal.RSI_BELOW_LOW: rsi_known & (rsi < RSI_LOW) & (rsi.shift(1) >= RSI_LOW),
        Signal.CROSS_ABOVE_SMA_200: sma_known & above & ~was_above,
        Signal.CROSS_BELOW_SMA_200: sma_known & ~above & was_above,
    }


def forward_returns(close: pd.Series, horizon_days: int) -> pd.Series:
    """Retorno de cada dia até `horizon_days` dias de CALENDÁRIO depois.

    Medido no calendário, não em linhas: se faltar o candle do fim do horizonte, o resultado
    daquele dia fica vazio em vez de usar outro dia sem avisar.
    """
    daily = close.asfreq("D")
    later = daily.shift(-horizon_days)
    return (later / daily - 1).reindex(close.index)


def independent_events(events: pd.Series, horizon_days: int) -> pd.Series:
    """Mantém um sinal e descarta os que caem dentro do horizonte dele (agrupamento).

    O laço percorre só os dias com sinal (dezenas), não a série inteira.
    """
    kept: list[pd.Timestamp] = []
    for ts in events.index[events.to_numpy(dtype=bool)]:
        if not kept or (ts - kept[-1]).days >= horizon_days:
            kept.append(ts)
    return pd.Series(events.index.isin(kept), index=events.index)


def evaluate(
    events: pd.Series,
    close: pd.Series,
    signal: Signal,
    horizon_days: int,
    min_sample: int,
) -> BacktestResult:
    """Resultado de um sinal num horizonte, ao lado da linha de base."""
    returns = forward_returns(close, horizon_days)
    independent = independent_events(events, horizon_days)
    outcomes = returns[independent].dropna()
    baseline = returns.dropna()
    enough = len(outcomes) >= min_sample
    event_days = events.index[events.to_numpy(dtype=bool)]
    return BacktestResult(
        signal=signal,
        horizon_days=horizon_days,
        raw_count=int(events.sum()),
        independent_count=int(independent.sum()),
        evaluated_count=len(outcomes),
        enough_sample=enough,
        mean_return=float(outcomes.mean()) if enough else None,
        median_return=float(outcomes.median()) if enough else None,
        hit_rate=float((outcomes > 0).mean()) if enough else None,
        baseline_mean=float(baseline.mean()) if not baseline.empty else None,
        baseline_hit_rate=float((baseline > 0).mean()) if not baseline.empty else None,
        first_event=event_days[0].to_pydatetime() if len(event_days) else None,
        last_event=event_days[-1].to_pydatetime() if len(event_days) else None,
    )


def run_backtest(
    close: pd.Series,
    rsi: pd.Series,
    sma_200: pd.Series,
    horizons_days: Sequence[int],
    min_sample: int,
) -> list[BacktestResult]:
    """Todos os sinais em todos os horizontes, para um ativo."""
    events = signal_events(close, rsi, sma_200)
    return [
        evaluate(events[signal], close, signal, horizon, min_sample)
        for signal in Signal
        for horizon in horizons_days
    ]
