from datetime import UTC, datetime

import numpy as np
import pandas as pd

from crypto_analyzer.config import QualityConfig
from crypto_analyzer.pipeline.quality import (
    check_gaps,
    check_invalid_prices,
    check_outliers,
    check_quality,
    check_staleness,
)

CONFIG = QualityConfig(outlier_threshold=10.0, max_age_hours={"1d": 48, "1h": 3})
NOW = datetime(2026, 10, 28, 12, tzinfo=UTC)


def make_frame(closes: list[float], start: str = "2026-10-01") -> pd.DataFrame:
    index = pd.date_range(start, periods=len(closes), freq="1D", tz="UTC", name="ts")
    close = pd.Series(closes, index=index, dtype="float64")
    return pd.DataFrame(
        {
            "open": close,
            "high": close + 1,
            "low": close - 1,
            "close": close,
            "volume": 1.0,
            "is_partial": False,
            "source_bronze_id": 1,
        }
    )


def wavy_closes(n: int) -> list[float]:
    """Preço com oscilação pequena e regular, sem nenhum outlier."""
    return [100 + 2 * np.sin(i) for i in range(n)]


def test_clean_data_has_no_issues() -> None:
    frame = make_frame(wavy_closes(27))  # termina em 2026-10-27

    assert check_quality(frame, "1d", NOW, CONFIG) == []


def test_empty_frame_is_reported_as_no_data() -> None:
    issues = check_quality(make_frame([]), "1d", NOW, CONFIG)

    assert [i.check for i in issues] == ["no_data"]


def test_invalid_prices_are_found() -> None:
    frame = make_frame(wavy_closes(5))
    frame.iloc[1, frame.columns.get_loc("close")] = -3.0  # preço negativo
    frame.iloc[3, frame.columns.get_loc("high")] = 0.5  # máxima abaixo da mínima/fechamento

    issues = check_invalid_prices(frame)

    assert [i.ts_start for i in issues] == [frame.index[1], frame.index[3]]


def test_gaps_are_grouped_into_runs() -> None:
    frame = make_frame(wavy_closes(10)).drop(frame_index(2, 3, 7))

    issues = check_gaps(frame, "1d")

    assert [(i.ts_start, i.ts_end, i.detail) for i in issues] == [
        (
            datetime(2026, 10, 3, tzinfo=UTC),
            datetime(2026, 10, 4, tzinfo=UTC),
            "2 candles faltando",
        ),
        (
            datetime(2026, 10, 8, tzinfo=UTC),
            datetime(2026, 10, 8, tzinfo=UTC),
            "1 candles faltando",
        ),
    ]


def frame_index(*offsets: int) -> pd.DatetimeIndex:
    start = pd.Timestamp("2026-10-01", tz="UTC")
    return pd.DatetimeIndex([start + pd.Timedelta(days=o) for o in offsets])


def test_an_abrupt_jump_is_an_outlier_but_normal_noise_is_not() -> None:
    closes = wavy_closes(40)
    closes[20] = closes[20] * 3  # sobe 200% e volta no dia seguinte
    frame = make_frame(closes)

    issues = check_outliers(frame, "1d", threshold=10.0)

    assert {i.ts_start for i in issues} == {
        frame.index[20].to_pydatetime(),
        frame.index[21].to_pydatetime(),
    }
    assert check_outliers(make_frame(wavy_closes(40)), "1d", threshold=10.0) == []


def test_partial_candle_is_not_judged_as_outlier() -> None:
    closes = wavy_closes(30)
    closes[-1] = closes[-1] * 3
    frame = make_frame(closes)
    frame.iloc[-1, frame.columns.get_loc("is_partial")] = True

    assert check_outliers(frame, "1d", threshold=10.0) == []


def test_return_across_a_gap_is_not_an_outlier() -> None:
    frame = make_frame(wavy_closes(40)).drop(frame_index(19, 20, 21))
    frame.loc[frame.index[19:], "close"] *= 1.5  # nível novo depois do buraco

    assert check_outliers(frame, "1d", threshold=10.0) == []


def test_stale_data_is_flagged_only_past_the_limit() -> None:
    frame = make_frame(wavy_closes(10), start="2026-10-20")  # último candle: 2026-10-29 00:00
    last = frame.index.max().to_pydatetime()

    assert check_staleness(frame, last.replace(hour=23), 48) == []
    issues = check_staleness(frame, datetime(2026, 11, 5, tzinfo=UTC), 48)
    assert [i.check for i in issues] == ["stale"]


def test_duplicates_removed_are_reported_as_info() -> None:
    frame = make_frame(wavy_closes(27))

    issues = check_quality(frame, "1d", NOW, CONFIG, duplicates_removed=3)

    assert [(i.check, i.severity) for i in issues] == [("duplicate", "info")]
