"""Gera o .xlsx de verdade e o lê de volta com openpyxl, como um usuário abriria."""

import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest
from openpyxl import load_workbook
from openpyxl.workbook.workbook import Workbook

from crypto_analyzer.reports.excel import default_report_path, write_report
from crypto_analyzer.reports.frames import (
    ReportData,
    candles_frame,
    indicators_frame,
    regime_changes_frame,
    summary_frame,
)
from tests.unit.report_data import build_report_data

SHEETS = [
    "Resumo",
    "Candles",
    "Indicadores",
    "Regimes",
    "Mudanças",
    "Backtest",
    "Qualidade",
    "Gráficos",
    "Sobre",
]


@pytest.fixture(scope="module")
def data() -> ReportData:
    return build_report_data()


@pytest.fixture(scope="module")
def report(data: ReportData, tmp_path_factory: pytest.TempPathFactory) -> Path:
    return write_report(data, tmp_path_factory.mktemp("output") / "sub" / "report.xlsx")


@pytest.fixture(scope="module")
def book(report: Path) -> Workbook:
    return load_workbook(report)


def header(book: Workbook, sheet: str) -> list[object]:
    return [cell.value for cell in book[sheet][1]]


def column(book: Workbook, sheet: str, name: str) -> list[object]:
    number = header(book, sheet).index(name) + 1
    return [
        row[0]
        for row in book[sheet].iter_rows(
            min_row=2, min_col=number, max_col=number, values_only=True
        )
    ]


def test_creates_the_folder_and_has_every_sheet_in_order(report: Path, book: Workbook) -> None:
    assert report.exists()
    assert book.sheetnames == SHEETS


def test_headers_and_row_counts_match_the_frames(data: ReportData, book: Workbook) -> None:
    for sheet, frame in (
        ("Resumo", summary_frame(data)),
        ("Candles", candles_frame(data)),
        ("Indicadores", indicators_frame(data)),
        ("Mudanças", regime_changes_frame(data)),
    ):
        assert header(book, sheet) == list(frame.columns), sheet
        assert book[sheet].max_row == len(frame) + 1, sheet


def test_dates_are_real_dates_and_prices_are_numbers(book: Workbook) -> None:
    for sheet in ("Candles", "Indicadores", "Regimes", "Mudanças"):
        assert all(isinstance(v, datetime) for v in column(book, sheet, "Data")), sheet
    for sheet, name in (
        ("Candles", "Fechamento (R$)"),
        ("Indicadores", "RSI 14"),
        ("Regimes", "Volatilidade diária"),
        ("Resumo", "Preço (R$)"),
    ):
        assert all(isinstance(v, int | float) for v in column(book, sheet, name)), (sheet, name)


def test_number_formats_show_reais_percent_and_dates(book: Workbook) -> None:
    resumo = book["Resumo"]
    names = header(book, "Resumo")
    price = resumo.cell(2, names.index("Preço (R$)") + 1)
    change = resumo.cell(2, names.index("Variação 1 dia") + 1)
    assert price.number_format == "R$ #,##0.00"
    assert change.number_format == "0.0%"
    date = book["Candles"].cell(2, header(book, "Candles").index("Data") + 1)
    assert date.number_format == "dd/mm/yyyy"


def test_no_empty_cells_except_btc_correlation(book: Workbook) -> None:
    """O único vazio esperado nas tabelas diárias é a correlação do BTC consigo mesmo."""
    for sheet in ("Candles", "Indicadores", "Regimes"):
        names = header(book, sheet)
        for row in book[sheet].iter_rows(min_row=2, values_only=True):
            for name, value in zip(names, row, strict=True):
                if value is None:
                    assert sheet == "Indicadores" and "Correlação" in str(name), (
                        sheet,
                        name,
                        row[0],
                    )
                    assert row[0] == "BTC"


def test_quality_keeps_empty_dates_only_where_there_are_none(book: Workbook) -> None:
    rows = list(book["Qualidade"].iter_rows(min_row=2, values_only=True))
    assert len(rows) == 2
    duplicate = next(r for r in rows if r[1] == "Candles repetidos")
    outlier = next(r for r in rows if r[1] == "Movimento extremo")
    assert duplicate[3] is None and duplicate[4] is None
    assert outlier[3] == datetime(2022, 11, 9)


def test_header_is_frozen_and_tables_have_filters(book: Workbook) -> None:
    assert book["Candles"].freeze_panes == "C2"
    assert book["Resumo"].freeze_panes == "B2"
    assert book["Sobre"].freeze_panes == "A2"
    for sheet in ("Resumo", "Candles", "Indicadores", "Regimes", "Mudanças", "Qualidade"):
        assert book[sheet].auto_filter.ref, sheet
    assert not book["Sobre"].auto_filter.ref


def test_regime_and_sign_columns_have_conditional_colors(book: Workbook) -> None:
    ranges = {str(rule.sqref) for rule in book["Regimes"].conditional_formatting}
    assert len(ranges) == 2  # Agitação do dia e Agitação confirmada
    assert book["Resumo"].conditional_formatting


def test_has_two_native_charts_per_asset_and_no_macros(data: ReportData, report: Path) -> None:
    with zipfile.ZipFile(report) as archive:
        names = archive.namelist()
    charts = [n for n in names if n.startswith("xl/charts/chart")]
    assert len(charts) == 2 * len(data.assets.symbols)
    assert not any("vbaProject" in n or "externalLink" in n for n in names)


def test_about_sheet_has_the_disclaimer(book: Workbook) -> None:
    values = dict(book["Sobre"].iter_rows(min_row=2, values_only=True))
    assert "não é recomendação de investimento" in str(values["Aviso"]).lower()
    assert values["Gerado em (UTC)"] == datetime(2026, 10, 29, 12)


def test_default_path_has_the_utc_date() -> None:
    path = default_report_path(Path("output"), datetime(2026, 10, 27, 23, tzinfo=UTC))
    assert path == Path("output/crypto_report_2026-10-27.xlsx")


def test_backtest_blanks_only_where_the_sample_is_too_small(book: Workbook) -> None:
    names = header(book, "Backtest")
    rows = list(book["Backtest"].iter_rows(min_row=2, values_only=True))
    enough = {row[names.index("Amostra suficiente")] for row in rows}

    assert enough == {"Sim", "Não"}  # os dados de teste têm os dois casos
    for row in rows:
        values = dict(zip(names, row, strict=True))
        assert isinstance(values["Ocorrências independentes"], int)  # contagem sempre presente
        assert isinstance(values["Retorno médio (qualquer dia)"], float)  # base sempre presente
        if values["Amostra suficiente"] == "Sim":
            assert isinstance(values["Retorno médio"], float)
        else:
            assert values["Retorno médio"] is None and values["Subiu em"] is None
    assert book["Backtest"].cell(2, names.index("Retorno médio") + 1).number_format == "0.0%"
