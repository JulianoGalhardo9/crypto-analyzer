"""Quando atualizar os candles de 1h de um ativo, conforme o regime dele (função pura)."""

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta

from crypto_analyzer.core.models import Regime

HOUR = timedelta(hours=1)


def refresh_due(
    regime: Regime | None,
    last_fetch: datetime | None,
    now: datetime,
    refresh_hours: Mapping[Regime, int],
) -> bool:
    """Se já passaram as horas do regime desde a última coleta de 1h.

    Conta horas cheias (01:05 e 02:04 estão a 1 hora de distância), porque a checagem roda
    sempre alguns minutos depois da hora cheia e a coleta anterior também. Sem coleta anterior,
    atualiza; sem regime conhecido, usa o intervalo de "high" (o mais curto).
    """
    if last_fetch is None:
        return True
    hours = refresh_hours[regime if regime is not None else Regime.HIGH]
    return (_hour(now) - _hour(last_fetch)) // HOUR >= hours


def _hour(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        raise ValueError("datas precisam de fuso horário (UTC)")
    return moment.astimezone(UTC).replace(minute=0, second=0, microsecond=0)
