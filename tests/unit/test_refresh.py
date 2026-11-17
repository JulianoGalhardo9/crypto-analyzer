from datetime import UTC, datetime, timedelta, timezone

import pytest

from crypto_analyzer.config import load_regime_config
from crypto_analyzer.core.models import Regime
from crypto_analyzer.core.refresh import refresh_due

HOURS = {Regime.CALM: 6, Regime.NORMAL: 3, Regime.HIGH: 1}
NOW = datetime(2026, 11, 17, 12, 5, 2, tzinfo=UTC)


def at(hour: int, minute: int = 5, second: int = 30) -> datetime:
    return datetime(2026, 11, 17, hour, minute, second, tzinfo=UTC)


@pytest.mark.parametrize(
    ("regime", "last", "due"),
    [
        (Regime.HIGH, at(11), True),  # 59 min e 32 s, mas a hora cheia mudou
        (Regime.HIGH, at(12, 0, 1), False),  # já coletado nesta hora
        (Regime.NORMAL, at(10), False),  # 2 horas
        (Regime.NORMAL, at(9), True),  # 3 horas
        (Regime.CALM, at(7), False),  # 5 horas
        (Regime.CALM, at(6), True),  # 6 horas
    ],
)
def test_interval_follows_the_regime(regime: Regime, last: datetime, due: bool) -> None:
    assert refresh_due(regime, last, NOW, HOURS) is due


def test_never_collected_is_due() -> None:
    assert refresh_due(Regime.CALM, None, NOW, HOURS)


def test_unknown_regime_uses_the_shortest_interval() -> None:
    assert refresh_due(None, at(11), NOW, HOURS)
    assert not refresh_due(None, at(12, 0, 1), NOW, HOURS)


def test_other_time_zones_are_compared_in_utc() -> None:
    brasilia = timezone(timedelta(hours=-3))
    last = datetime(2026, 11, 17, 8, 5, tzinfo=brasilia)  # 11:05 UTC

    assert refresh_due(Regime.HIGH, last, NOW, HOURS)


def test_naive_dates_are_refused() -> None:
    with pytest.raises(ValueError, match="fuso"):
        refresh_due(Regime.HIGH, datetime(2026, 11, 17, 11), NOW, HOURS)


def test_regimes_yaml_has_an_interval_for_every_regime() -> None:
    hours = load_regime_config().refresh_hours

    assert set(hours) == set(Regime)
    assert hours[Regime.HIGH] <= hours[Regime.NORMAL] <= hours[Regime.CALM]
