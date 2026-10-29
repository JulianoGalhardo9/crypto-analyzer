from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pandas as pd

from crypto_analyzer.config import QualityConfig
from crypto_analyzer.pipeline.silver import PRICE_COLUMNS, STEP

# Fator que faz o MAD (desvio absoluto mediano) equivaler a um desvio padrão numa normal.
MAD_SCALE = 1.4826


@dataclass(frozen=True)
class QualityIssue:
    check: str  # duplicate | invalid_price | gap | outlier | stale | no_data
    severity: str  # info | warning | error
    ts_start: datetime | None
    ts_end: datetime | None
    detail: str


def check_quality(
    frame: pd.DataFrame,
    resolution: str,
    now: datetime,
    config: QualityConfig,
    *,
    duplicates_removed: int = 0,
) -> list[QualityIssue]:
    """Roda todas as checagens sobre os candles da silver e devolve os problemas achados."""
    if frame.empty:
        return [QualityIssue("no_data", "error", None, None, "nenhum candle disponível")]

    issues: list[QualityIssue] = []
    if duplicates_removed:
        issues.append(
            QualityIssue(
                "duplicate",
                "info",
                None,
                None,
                f"{duplicates_removed} candles repetidos entre coletas; ficou o mais recente",
            )
        )
    issues += check_invalid_prices(frame)
    issues += check_gaps(frame, resolution)
    issues += check_outliers(frame, resolution, config.outlier_threshold)
    issues += check_staleness(frame, now, config.max_age_hours[resolution])
    return issues


def invalid_price_mask(frame: pd.DataFrame) -> pd.Series:
    """True onde o candle é impossível: preço <= 0/ausente ou máxima/mínima incoerentes."""
    prices = frame[PRICE_COLUMNS]
    non_positive = (prices.isna() | (prices <= 0)).any(axis=1)
    high_too_low = frame["high"] < frame[["open", "close", "low"]].max(axis=1)
    low_too_high = frame["low"] > frame[["open", "close", "high"]].min(axis=1)
    return non_positive | high_too_low | low_too_high


def check_invalid_prices(frame: pd.DataFrame) -> list[QualityIssue]:
    return [
        QualityIssue(
            "invalid_price", "error", ts.to_pydatetime(), ts.to_pydatetime(), "OHLC incoerente"
        )
        for ts in frame.index[invalid_price_mask(frame)]
    ]


def check_gaps(frame: pd.DataFrame, resolution: str) -> list[QualityIssue]:
    """Acha candles faltando entre o primeiro e o último e agrupa os buracos seguidos."""
    step = STEP[resolution]
    expected = pd.date_range(frame.index.min(), frame.index.max(), freq=step)
    missing = pd.Series(expected.difference(pd.DatetimeIndex(frame.index)))
    if missing.empty:
        return []

    # Cada vez que a distância até o anterior deixa de ser 1 passo, começa um buraco novo.
    gap_id = (missing.diff() != step).cumsum()
    issues = []
    for _, run in missing.groupby(gap_id):
        start, end = run.iloc[0], run.iloc[-1]
        issues.append(
            QualityIssue(
                "gap",
                "warning",
                start.to_pydatetime(),
                end.to_pydatetime(),
                f"{len(run)} candles faltando",
            )
        )
    return issues


def check_outliers(frame: pd.DataFrame, resolution: str, threshold: float) -> list[QualityIssue]:
    """Movimentos extremos, usando mediana e MAD (que o próprio outlier não distorce).

    Severidade `info`: nos dados reais isto acha eventos verdadeiros (ex.: queda de 42% da SOL
    em 2022-11-09), então é um aviso para olhar, nunca motivo para apagar o candle.

    Ficam de fora: candles inválidos, o candle parcial e retornos que atravessam um buraco
    (não são de um único passo).
    """
    candidates = frame.loc[~invalid_price_mask(frame) & ~frame["is_partial"]]
    log_return = np.log(candidates["close"]).diff()
    one_step = candidates.index.to_series().diff() == STEP[resolution]
    log_return = log_return.where(one_step).dropna()
    if log_return.empty:
        return []

    center = log_return.median()
    mad = (log_return - center).abs().median()
    if mad == 0:
        return []

    score = (log_return - center).abs() / (MAD_SCALE * mad)
    return [
        QualityIssue(
            "outlier",
            "info",
            ts.to_pydatetime(),
            ts.to_pydatetime(),
            f"movimento extremo de {np.expm1(log_return[ts]):+.1%} "
            f"({score[ts]:.1f}x o normal); pode ser real",
        )
        for ts in score.index[score > threshold]
    ]


def check_staleness(frame: pd.DataFrame, now: datetime, max_age_hours: float) -> list[QualityIssue]:
    last = frame.index.max()
    age = pd.Timestamp(now) - last
    if age <= pd.Timedelta(hours=max_age_hours):
        return []
    return [
        QualityIssue(
            "stale",
            "warning",
            last.to_pydatetime(),
            None,
            f"último candle tem {age / pd.Timedelta(hours=1):.1f}h (limite {max_age_hours:g}h)",
        )
    ]
