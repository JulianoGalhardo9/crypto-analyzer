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
    now = datetime(2026, 10, 29, 12, tzinfo=UTC)

    result = build_silver([new, old], "1d", now)  # fora de ordem de propósito

    assert result.duplicates_removed == 1
    assert list(result.frame["close"]) == [10.0, 20.0, 20.0]
    assert list(result.frame["source_bronze_id"]) == [1, 2, 2]
    assert result.frame.index.is_monotonic_increasing


def test_only_the_candle_still_open_is_partial() -> None:
    now = datetime(2026, 10, 28, 15, tzinfo=UTC)  # meio do dia 28
    result = build_silver([response(1, 10, [T0, T0 + DAY, T0 + 2 * DAY], 10.0)], "1d", now)

    assert list(result.frame["is_partial"]) == [False, False, True]


def test_no_responses_gives_an_empty_typed_frame() -> None:
    result = build_silver([], "1d", datetime(2026, 10, 28, tzinfo=UTC))

    assert result.frame.empty
    assert str(result.frame.index.tz) == "UTC"
    assert result.frame["close"].dtype == "float64"
