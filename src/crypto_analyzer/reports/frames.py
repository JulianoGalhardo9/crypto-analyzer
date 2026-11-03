"""Monta os DataFrames de cada aba da planilha (puro, sem I/O nem Excel).

Formato "longo": uma coluna `Ativo` e uma linha por ativo e dia, ordenadas por ativo e data.
Assim o usuário pode filtrar, ordenar e criar tabelas dinâmicas. Datas são datas de verdade
(sem fuso: o Excel não aceita fuso; elas representam dias em UTC, como diz a aba Sobre).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pandas as pd

from crypto_analyzer.config import AssetsConfig
from crypto_analyzer.core.models import Analysis, Regime, Trend

DISCLAIMER = "Informativo, não é recomendação de investimento."
SOURCE = "Mercado Bitcoin, API pública v4 (candles diários, cotados em BRL)"

TREND_NAMES = {Trend.UP: "Subindo", Trend.SIDEWAYS: "De lado", Trend.DOWN: "Caindo"}
REGIME_NAMES = {Regime.CALM: "Calma", Regime.NORMAL: "Normal", Regime.HIGH: "Alta"}
REGIME_BY_VALUE = {regime.value: name for regime, name in REGIME_NAMES.items()}
CHECK_NAMES = {
    "outlier": "Movimento extremo",
    "gap": "Buraco nos candles",
    "invalid_price": "Preço inválido",
    "stale": "Dado desatualizado",
    "duplicate": "Candles repetidos",
    "no_data": "Sem dados",
}
SEVERITY_NAMES = {"info": "Informativo", "warning": "Alerta", "error": "Erro"}


@dataclass(frozen=True)
class QualityRecord:
    symbol: str
    check: str
    severity: str
    ts_start: datetime | None
    ts_end: datetime | None
    detail: str


@dataclass(frozen=True)
class ReportData:
    """O que a planilha precisa, já lido do banco (dicionários por par, ex.: SOL-BRL)."""

    assets: AssetsConfig
    candles: Mapping[str, pd.DataFrame]  # candles fechados: open, high, low, close, volume
    indicators: Mapping[str, pd.DataFrame]  # fact_indicador
    regimes: Mapping[str, pd.DataFrame]  # fact_regime
    quality: Sequence[QualityRecord]
    analyses: Sequence[Analysis]
    generated_at: datetime
    window_days: int


def summary_frame(data: ReportData) -> pd.DataFrame:
    """Aba Resumo: uma linha por ativo."""
    rows = [
        {
            "Ativo": a.base,
            "Nome": a.name,
            "Último dia fechado": _naive(a.as_of),
            "Preço (R$)": a.price,
            "Variação 1 dia": a.change_1d,
            "Variação 7 dias": a.change_7d,
            "Variação 30 dias": a.change_30d,
            "Tendência": TREND_NAMES.get(a.trend, "Sem histórico") if a.trend else "Sem histórico",
            "Agitação": REGIME_NAMES[a.regime] if a.regime else "Sem histórico",
            "Percentil da volatilidade": a.volatility_percentile,
            "RSI 14": a.rsi_14,
            "Correlação com o BTC (90 dias)": a.corr_btc_90,
        }
        for a in data.analyses
    ]
    return pd.DataFrame(rows)


def candles_frame(data: ReportData) -> pd.DataFrame:
    """Aba Candles: candles diários fechados dos últimos `window_days`."""
    return _stack(
        data,
        data.candles,
        {
            "open": "Abertura (R$)",
            "high": "Máxima (R$)",
            "low": "Mínima (R$)",
            "close": "Fechamento (R$)",
            "volume": "Volume",
        },
    )


def indicators_frame(data: ReportData) -> pd.DataFrame:
    """Aba Indicadores: o fechamento e todos os indicadores, por ativo e dia."""
    joined = {
        symbol: pd.concat([data.candles[symbol][["close"]], data.indicators[symbol]], axis=1)
        for symbol in data.candles
    }
    return _stack(
        data,
        joined,
        {
            "close": "Fechamento (R$)",
            "sma_20": "Média 20 dias",
            "sma_50": "Média 50 dias",
            "sma_200": "Média 200 dias",
            "ema_12": "EMA 12",
            "ema_26": "EMA 26",
            "rsi_14": "RSI 14",
            "macd": "MACD",
            "macd_signal": "Sinal do MACD",
            "macd_histogram": "Histograma do MACD",
            "atr_14": "ATR 14 (R$)",
            "bb_lower": "Bollinger inferior",
            "bb_middle": "Bollinger central",
            "bb_upper": "Bollinger superior",
            "corr_btc_90": "Correlação com o BTC (90 dias)",
        },
    )


def regimes_frame(data: ReportData) -> pd.DataFrame:
    """Aba Regimes: volatilidade, percentil e regime por ativo e dia."""
    frame = _stack(
        data,
        data.regimes,
        {
            "volatility": "Volatilidade diária",
            "volatility_percentile": "Percentil da volatilidade",
            "raw_regime": "Agitação do dia",
            "regime": "Agitação confirmada",
        },
    )
    for column in ("Agitação do dia", "Agitação confirmada"):
        frame[column] = frame[column].map(REGIME_BY_VALUE)
    return frame


def regime_changes_frame(data: ReportData) -> pd.DataFrame:
    """Aba Mudanças: cada vez que o regime confirmado mudou, em todo o histórico."""
    rows = []
    for symbol in data.regimes:
        regime = data.regimes[symbol]["regime"].dropna()
        values = regime.to_numpy(dtype=object)
        dates = pd.DatetimeIndex(regime.index)
        # posições onde o regime é diferente do dia anterior = onde um regime novo começa
        changes = (np.flatnonzero(values[1:] != values[:-1]) + 1).tolist()
        run_starts = [0, *changes]
        for number, position in enumerate(changes):
            rows.append(
                {
                    "Ativo": _label(data, symbol),
                    "Data": _naive(dates[position]),
                    "Regime anterior": REGIME_BY_VALUE[values[position - 1]],
                    "Novo regime": REGIME_BY_VALUE[values[position]],
                    "Dias no regime anterior": (dates[position] - dates[run_starts[number]]).days,
                }
            )
    return pd.DataFrame(
        rows,
        columns=["Ativo", "Data", "Regime anterior", "Novo regime", "Dias no regime anterior"],
    )


def quality_frame(data: ReportData) -> pd.DataFrame:
    """Aba Qualidade: o que as checagens de qualidade encontraram."""
    rows = [
        {
            "Ativo": _label(data, record.symbol),
            "Verificação": CHECK_NAMES.get(record.check, record.check),
            "Gravidade": SEVERITY_NAMES.get(record.severity, record.severity),
            "Início": _naive(record.ts_start) if record.ts_start else pd.NaT,
            "Fim": _naive(record.ts_end) if record.ts_end else pd.NaT,
            "Detalhe": record.detail,
        }
        for record in data.quality
    ]
    frame = pd.DataFrame(
        rows, columns=["Ativo", "Verificação", "Gravidade", "Início", "Fim", "Detalhe"]
    )
    for column in ("Início", "Fim"):
        frame[column] = pd.to_datetime(frame[column])
    return frame.sort_values(["Ativo", "Verificação", "Início"], kind="stable", ignore_index=True)


def about_frame(data: ReportData) -> pd.DataFrame:
    """Aba Sobre: de onde vêm os dados, a janela usada e o aviso."""
    last_day = max(a.as_of for a in data.analyses)
    oldest_hours = max(a.data_age_hours for a in data.analyses)
    stale = any(a.is_stale for a in data.analyses)
    rows: list[tuple[str, object]] = [
        ("Gerado em (UTC)", _naive(data.generated_at)),
        ("Fonte dos dados", SOURCE),
        ("Último dia fechado", _naive(last_day)),
        (
            "Atualidade dos dados",
            f"ATENÇÃO: o candle mais recente tem {oldest_hours / 24:.0f} dias"
            if stale
            else "Dados recentes",
        ),
        ("Janela exibida (dias)", data.window_days),
        ("Resolução", "Diária (1d), dias em UTC"),
        ("Datas", "São dias em UTC, sem fuso horário"),
        ("Indicadores", "Calculados sobre todo o histórico disponível de cada ativo"),
        ("Rótulos de agitação", "Percentil da volatilidade nos últimos 365 dias do próprio ativo"),
        ("Aviso", DISCLAIMER),
    ]
    return pd.DataFrame(rows, columns=["Campo", "Valor"])


# --- auxiliares ---


def _stack(
    data: ReportData, frames: Mapping[str, pd.DataFrame], columns: Mapping[str, str]
) -> pd.DataFrame:
    """Empilha os ativos (ordem de `assets.yaml`) e mantém só a janela recente de cada um."""
    parts = []
    for symbol in data.assets.symbols:
        recent = frames[symbol].iloc[-data.window_days :][list(columns)].rename(columns=columns)
        recent.insert(0, "Data", _naive_index(recent.index))
        recent.insert(0, "Ativo", _label(data, symbol))
        parts.append(recent.reset_index(drop=True))
    return pd.concat(parts, ignore_index=True)


def _label(data: ReportData, symbol: str) -> str:
    return symbol.removesuffix(f"-{data.assets.quote}")


def _naive(moment: datetime | pd.Timestamp) -> pd.Timestamp:
    """Data UTC sem fuso (o Excel não aceita fuso)."""
    stamp = pd.Timestamp(moment)
    return stamp.tz_convert("UTC").tz_localize(None) if stamp.tzinfo else stamp


def _naive_index(index: pd.Index) -> pd.DatetimeIndex:
    return pd.DatetimeIndex(index).tz_convert("UTC").tz_localize(None)
