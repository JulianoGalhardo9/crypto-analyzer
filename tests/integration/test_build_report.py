from datetime import UTC, datetime
from pathlib import Path

import pytest
from openpyxl import load_workbook
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from crypto_analyzer.config import QualityConfig, ReportConfig, load_regime_config
from crypto_analyzer.infra.db import make_session_factory
from crypto_analyzer.infra.repositories import replace_quality_issues
from crypto_analyzer.pipeline.build_analysis import NoDataError
from crypto_analyzer.pipeline.build_report import build_report_data
from crypto_analyzer.pipeline.process_gold import process_gold
from crypto_analyzer.pipeline.quality import QualityIssue
from crypto_analyzer.reports.excel import write_report
from tests.integration.helpers import ASSETS, seed_silver

pytestmark = pytest.mark.integration

QUALITY = QualityConfig(outlier_threshold=10.0, max_age_hours={"1d": 48, "1h": 3})
REPORT = ReportConfig(window_days=30)
NOW = datetime(2026, 10, 5, 12, tzinfo=UTC)


def prepare(engine: Engine, session: Session) -> None:
    seed_silver(session, "BTC-BRL", seed=1)
    seed_silver(session, "SOL-BRL", seed=2)
    replace_quality_issues(
        session,
        "SOL-BRL",
        "1d",
        [QualityIssue("gap", "warning", NOW, NOW, "1 candle faltando")],
    )
    replace_quality_issues(
        session, "SOL-BRL", "1h", [QualityIssue("stale", "info", None, None, "horário")]
    )
    session.commit()
    process_gold(make_session_factory(engine), ASSETS, load_regime_config())


def test_report_data_is_read_from_the_database(engine: Engine, session: Session) -> None:
    prepare(engine, session)

    data = build_report_data(
        make_session_factory(engine), ASSETS, NOW, QUALITY, load_regime_config(), REPORT
    )

    assert [a.base for a in data.analyses] == ["BTC", "SOL"]
    assert set(data.candles) == set(data.indicators) == set(data.regimes) == {"BTC-BRL", "SOL-BRL"}
    # o candle parcial (último dia) não entra
    assert data.candles["SOL-BRL"].index.max() == datetime(2026, 10, 4, tzinfo=UTC)
    # só a qualidade dos candles diários
    assert [(q.symbol, q.check) for q in data.quality] == [("SOL-BRL", "gap")]
    assert data.window_days == 30 and data.generated_at == NOW


def test_report_from_the_database_is_a_valid_workbook(
    engine: Engine, session: Session, tmp_path: Path
) -> None:
    prepare(engine, session)
    data = build_report_data(
        make_session_factory(engine), ASSETS, NOW, QUALITY, load_regime_config(), REPORT
    )

    book = load_workbook(write_report(data, tmp_path / "report.xlsx"))

    assert book["Resumo"].max_row == 3  # cabeçalho + BTC + SOL
    assert book["Candles"].max_row == 1 + 2 * 30
    assert book["Qualidade"]["B2"].value == "Buraco nos candles"
    header = [cell.value for cell in book["Regimes"][1]]
    column = header.index("Agitação confirmada")
    labels = {row[column] for row in book["Regimes"].iter_rows(min_row=2, values_only=True)}
    assert labels and labels <= {"Calma", "Normal", "Alta"}


def test_missing_gold_raises_no_data_error(engine: Engine, session: Session) -> None:
    seed_silver(session, "BTC-BRL", seed=1)

    with pytest.raises(NoDataError):
        build_report_data(
            make_session_factory(engine), ASSETS, NOW, QUALITY, load_regime_config(), REPORT
        )
