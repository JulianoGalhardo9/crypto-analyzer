import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

from crypto_analyzer.pipeline.silver import BronzeResponse, build_silver, parse_payload

FIXTURE = Path(__file__).parent.parent / "fixtures" / "candles_sol_brl_1d.json"
DAY = 86_400
T0 = 1_792_972_800  # 2026-10-26 00:00 UTC


def payload(timestamps: list[int], close: float = 10.0) -> dict[str, list[object]]:
    n = len(timestamps)
    return {
        "t": timestamps,
        "o": [str(close)] * n,
        "h": [str(close + 1)] * n,
        "l": [str(close - 1)] * n,
        "c": [str(close)] * n,
        "v": ["5.0"] * n,
    }


def response(bronze_id: int, hour: int, timestamps: list[int], close: float) -> BronzeResponse:
    return BronzeResponse(
        bronze_id, datetime(2026, 10, 28, hour, tzinfo=UTC), payload(timestamps, close)
    )


def test_parse_payload_gives_utc_index_and_float_columns() -> None:
    frame = parse_payload(json.loads(FIXTURE.read_text()))

    assert str(frame.index.tz) == "UTC"
    assert frame.index.name == "ts"
    assert frame.index[0] == pd.Timestamp("2026-10-26", tz="UTC")
    assert (frame.dtypes == "float64").all()
    assert frame["close"].iloc[0] == pytest.approx(541.77)


def test_parse_payload_rejects_missing_keys_and_uneven_lists() -> None:
    with pytest.raises(ValueError, match="faltam"):
        parse_payload({"t": [1]})
    broken = payload([T0, T0 + DAY])
    broken["c"] = ["1.0"]
    with pytest.raises(ValueError, match="tamanhos"):
        parse_payload(broken)


def test_newest_response_wins_on_duplicated_timestamps() -> None:
    old = response(1, 10, [T0, T0 + DAY], close=10.0)
    new = response(2, 18, [T0 + DAY, T0 + 2 * DAY], close=20.0)
    result = build_silver([new, old], "1d")  # fora de ordem de propósito

    assert result.duplicates_removed == 1
    assert list(result.frame["close"]) == [10.0, 20.0, 20.0]
    assert list(result.frame["source_bronze_id"]) == [1, 2, 2]
    assert result.frame.index.is_monotonic_increasing


def test_only_the_candle_still_open_when_fetched_is_partial() -> None:
    # coletado às 10h do dia 28: o candle do dia 28 ainda estava em formação
    result = build_silver([response(1, 10, [T0, T0 + DAY, T0 + 2 * DAY], 10.0)], "1d")

    assert list(result.frame["is_partial"]) == [False, False, True]


def test_a_candle_fetched_mid_day_stays_partial_no_matter_when_it_is_processed() -> None:
    # Bug real (2026-11-03): o candle do dia 29 foi coletado às 21h do próprio dia 29 e,
    # processado dias depois, era marcado como fechado. O que vale é a hora da COLETA.
    fetched_mid_day = BronzeResponse(
        1, datetime(2026, 10, 29, 21, tzinfo=UTC), payload([T0 + 3 * DAY], close=10.0)
    )

    result = build_silver([fetched_mid_day], "1d")

    assert list(result.frame["is_partial"]) == [True]


def test_a_later_fetch_completes_a_candle_that_was_partial() -> None:
    mid_day = BronzeResponse(
        1, datetime(2026, 10, 29, 21, tzinfo=UTC), payload([T0 + 3 * DAY], close=10.0)
    )
    next_day = BronzeResponse(
        2, datetime(2026, 10, 30, 8, tzinfo=UTC), payload([T0 + 3 * DAY], close=12.0)
    )

    result = build_silver([mid_day, next_day], "1d")

    assert list(result.frame["is_partial"]) == [False]
    assert list(result.frame["close"]) == [12.0]
    assert list(result.frame["source_bronze_id"]) == [2]


def test_no_responses_gives_an_empty_typed_frame() -> None:
    result = build_silver([], "1d")

    assert result.frame.empty
    assert str(result.frame.index.tz) == "UTC"
    assert result.frame["close"].dtype == "float64"
