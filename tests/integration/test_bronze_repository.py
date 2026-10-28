import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from crypto_analyzer.infra.repositories import save_raw_candles
from crypto_analyzer.infra.tables import BronzeCandlesRaw
from crypto_analyzer.pipeline.market_data import RawCandles

pytestmark = pytest.mark.integration

FIXTURE = Path(__file__).parent.parent / "fixtures" / "candles_sol_brl_1d.json"


def make_raw() -> RawCandles:
    return RawCandles(
        symbol="SOL-BRL",
        resolution="1d",
        params={"symbol": "SOL-BRL", "resolution": "1d", "to": 1793145600, "countback": 3},
        payload=json.loads(FIXTURE.read_text()),
        fetched_at=datetime(2026, 10, 28, 12, 0, tzinfo=UTC),
    )


def test_save_raw_candles_round_trips_the_payload_untouched(session: Session) -> None:
    raw = make_raw()

    row_id = save_raw_candles(session, raw)
    session.commit()

    row = session.scalars(select(BronzeCandlesRaw).where(BronzeCandlesRaw.id == row_id)).one()
    assert row.payload == raw.payload
    assert row.request_params == dict(raw.params)
    assert row.symbol == "SOL-BRL"
    assert row.fetched_at == raw.fetched_at
    assert row.ingested_at.tzinfo is not None


def test_each_call_appends_a_new_row(session: Session) -> None:
    save_raw_candles(session, make_raw())
    save_raw_candles(session, make_raw())
    session.commit()

    rows = session.scalars(select(BronzeCandlesRaw)).all()
    assert len(rows) == 2
