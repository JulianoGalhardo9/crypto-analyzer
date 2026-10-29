import copy
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from crypto_analyzer.config import QualityConfig
from crypto_analyzer.infra.db import make_session_factory
from crypto_analyzer.infra.repositories import save_raw_candles
from crypto_analyzer.infra.tables import QualityIssueRow, SilverCandle
from crypto_analyzer.pipeline.market_data import RawCandles
from crypto_analyzer.pipeline.process import process_silver

pytestmark = pytest.mark.integration

FIXTURE = Path(__file__).parent.parent / "fixtures" / "candles_sol_brl_1d.json"
CONFIG = QualityConfig(outlier_threshold=10.0, max_age_hours={"1d": 48, "1h": 3})
NOW = datetime(2026, 10, 28, 15, tzinfo=UTC)  # meio do dia do último candle da fixture


def add_bronze(
    session: Session, hour: int, payload: dict[str, list[str]], symbol: str = "SOL-BRL"
) -> int:
    raw = RawCandles(
        symbol=symbol,
        resolution="1d",
        params={},
        payload=payload,  # type: ignore[arg-type]
        fetched_at=datetime(2026, 10, 28, hour, tzinfo=UTC),
    )
    row_id = save_raw_candles(session, raw)
    session.commit()
    return row_id


def silver_rows(session: Session) -> list[SilverCandle]:
    return list(session.scalars(select(SilverCandle).order_by(SilverCandle.ts)))


def test_process_writes_silver_with_exact_decimals_and_partial_flag(
    engine: Engine, session: Session
) -> None:
    bronze_id = add_bronze(session, 10, json.loads(FIXTURE.read_text()))

    summaries = process_silver(make_session_factory(engine), ["SOL-BRL"], "1d", NOW, CONFIG)

    rows = silver_rows(session)
    assert [r.is_partial for r in rows] == [False, False, True]
    assert rows[0].close == Decimal("541.77000000")
    assert rows[0].ts == datetime(2026, 10, 26, tzinfo=UTC)
    assert {r.source_bronze_id for r in rows} == {bronze_id}
    assert (summaries[0].candles, summaries[0].partial) == (3, 1)


def test_processing_twice_does_not_duplicate_anything(engine: Engine, session: Session) -> None:
    add_bronze(session, 10, json.loads(FIXTURE.read_text()))
    factory = make_session_factory(engine)

    process_silver(factory, ["SOL-BRL"], "1d", NOW, CONFIG)
    first_issues = session.scalar(select(func.count()).select_from(QualityIssueRow))
    process_silver(factory, ["SOL-BRL"], "1d", NOW, CONFIG)

    assert len(silver_rows(session)) == 3
    assert session.scalar(select(func.count()).select_from(QualityIssueRow)) == first_issues


def test_newer_collection_updates_the_open_candle(engine: Engine, session: Session) -> None:
    payload = json.loads(FIXTURE.read_text())
    add_bronze(session, 10, payload)
    factory = make_session_factory(engine)
    process_silver(factory, ["SOL-BRL"], "1d", NOW, CONFIG)

    newer = copy.deepcopy(payload)
    newer["c"][-1] = "560.00000000"  # o candle do dia fechou em outro valor
    newer_id = add_bronze(session, 20, newer)
    process_silver(factory, ["SOL-BRL"], "1d", NOW, CONFIG)

    last = silver_rows(session)[-1]
    assert len(silver_rows(session)) == 3
    assert last.close == Decimal("560.00000000")
    assert last.source_bronze_id == newer_id
    duplicates = session.scalars(
        select(QualityIssueRow).where(QualityIssueRow.check_name == "duplicate")
    ).all()
    assert len(duplicates) == 1


def test_symbol_without_bronze_data_is_reported_not_crashed(
    engine: Engine, session: Session
) -> None:
    summaries = process_silver(make_session_factory(engine), ["BTC-BRL"], "1d", NOW, CONFIG)

    assert summaries[0].candles == 0
    assert summaries[0].issues_by_check == {"no_data": 1}
    assert silver_rows(session) == []
