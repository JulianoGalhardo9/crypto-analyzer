"""Escreve a planilha .xlsx com XlsxWriter: formatação, filtros, cores e gráficos nativos.

Os dados vêm prontos de `frames.py`; aqui só se decide como mostrá-los. Sem macros e sem
links externos: o arquivo abre em qualquer Excel/LibreOffice sem avisos de segurança.
"""

from datetime import datetime
from pathlib import Path

import pandas as pd
from xlsxwriter.chart import Chart
from xlsxwriter.workbook import Workbook
from xlsxwriter.worksheet import Worksheet

from crypto_analyzer import __version__
from crypto_analyzer.reports.frames import (
    ReportData,
    about_frame,
    candles_frame,
    indicators_frame,
    quality_frame,
    regime_changes_frame,
    regimes_frame,
    summary_frame,
)

# Formato de número de cada coluna, pelo nome exato do cabeçalho.
MONEY = "R$ #,##0.00"
NUMBER = "#,##0.00"
PERCENT = "0.0%"
PERCENT_2 = "0.00%"
DATE = "dd/mm/yyyy"
INTEGER = "0"
COLUMN_FORMATS: dict[str, str] = {
    "Último dia fechado": DATE,
    "Data": DATE,
    "Início": DATE,
    "Fim": DATE,
    "Preço (R$)": MONEY,
    "Abertura (R$)": MONEY,
    "Máxima (R$)": MONEY,
    "Mínima (R$)": MONEY,
    "Fechamento (R$)": MONEY,
    "ATR 14 (R$)": MONEY,
    "Média 20 dias": MONEY,
    "Média 50 dias": MONEY,
    "Média 200 dias": MONEY,
    "EMA 12": MONEY,
    "EMA 26": MONEY,
    "Bollinger inferior": MONEY,
    "Bollinger central": MONEY,
    "Bollinger superior": MONEY,
    "Variação 1 dia": PERCENT,
    "Variação 7 dias": PERCENT,
    "Variação 30 dias": PERCENT,
    "Volatilidade diária": PERCENT_2,
    "Volume": "#,##0.0000",
    "MACD": NUMBER,
    "Sinal do MACD": NUMBER,
    "Histograma do MACD": NUMBER,
    "RSI 14": "0.0",
    "Percentil da volatilidade": "0",
    "Correlação com o BTC (90 dias)": "0.00",
    "Dias no regime anterior": INTEGER,
    "Janela exibida (dias)": INTEGER,
    "Gerado em (UTC)": "dd/mm/yyyy hh:mm",
}
# Colunas com cor: regimes (por texto) e valores positivos/negativos.
REGIME_COLUMNS = {
    "Agitação",
    "Agitação do dia",
    "Agitação confirmada",
    "Regime anterior",
    "Novo regime",
}
SIGNED_COLUMNS = {"Variação 1 dia", "Variação 7 dias", "Variação 30 dias", "Histograma do MACD"}
WIDE_COLUMNS = {"Detalhe": 70, "Valor": 90, "Campo": 28, "Fonte dos dados": 50}
# Quantas colunas ficam congeladas à esquerda além do cabeçalho (Ativo e Data).
FROZEN_COLUMNS = {"Resumo": 1, "Candles": 2, "Indicadores": 2, "Regimes": 2}

GREEN, YELLOW, RED = "#C6EFCE", "#FFEB9C", "#FFC7CE"
GREEN_TEXT, RED_TEXT = "#006100", "#9C0006"


def write_report(data: ReportData, path: Path) -> Path:
    """Gera a planilha completa em `path` (cria a pasta, se preciso) e devolve o caminho."""
    path.parent.mkdir(parents=True, exist_ok=True)
    sheets: list[tuple[str, pd.DataFrame]] = [
        ("Resumo", summary_frame(data)),
        ("Candles", candles_frame(data)),
        ("Indicadores", indicators_frame(data)),
        ("Regimes", regimes_frame(data)),
        ("Mudanças", regime_changes_frame(data)),
        ("Qualidade", quality_frame(data)),
    ]
    about = about_frame(data)

    with pd.ExcelWriter(path, engine="xlsxwriter", datetime_format=DATE) as writer:
        workbook: Workbook = writer.book
        workbook.set_properties(
            {"title": "Análise de criptomoedas", "author": f"crypto-analyzer {__version__}"}
        )
        for name, frame in sheets:
            _write_table(writer, workbook, name, frame)
        _write_charts(workbook, data, sheets)
        _write_table(writer, workbook, "Sobre", about)
    return path


def default_report_path(directory: Path, now: datetime) -> Path:
    """`output/crypto_report_2026-10-27.xlsx`: o nome leva a data (UTC) da geração."""
    return directory / f"crypto_report_{now:%Y-%m-%d}.xlsx"


# --- tabelas ---


def _write_table(
    writer: pd.ExcelWriter, workbook: Workbook, name: str, frame: pd.DataFrame
) -> None:
    frame.to_excel(writer, sheet_name=name, index=False)
    sheet: Worksheet = writer.sheets[name]
    header = workbook.add_format(
        {
            "bold": True,
            "bg_color": "#1F3864",
            "font_color": "#FFFFFF",
            "valign": "vcenter",
            "text_wrap": True,
            "border": 1,
        }
    )
    rows = len(frame)

    for number, column in enumerate(frame.columns):
        sheet.write(0, number, column, header)
        cell_format = (
            workbook.add_format({"num_format": COLUMN_FORMATS[column]})
            if (column in COLUMN_FORMATS)
            else None
        )
        sheet.set_column(number, number, _width(column, frame[column]), cell_format)
        if column in REGIME_COLUMNS and rows:
            _color_regimes(workbook, sheet, number, rows)
        if column in SIGNED_COLUMNS and rows:
            _color_signs(workbook, sheet, number, rows)

    sheet.set_row(0, 30)
    sheet.freeze_panes(1, FROZEN_COLUMNS.get(name, 0))
    if name != "Sobre":
        sheet.autofilter(0, 0, max(rows, 1), len(frame.columns) - 1)
    if name == "Sobre":
        sheet.set_column(
            1, 1, WIDE_COLUMNS["Valor"], workbook.add_format({"text_wrap": True, "align": "left"})
        )


def _width(column: str, values: pd.Series) -> float:
    if column in WIDE_COLUMNS:
        return float(WIDE_COLUMNS[column])
    longest = max([len(str(column)), *(len(str(v)) for v in values.head(200).dropna())])
    return float(min(max(longest + 3, 12), 34))


def _color_regimes(workbook: Workbook, sheet: Worksheet, column: int, rows: int) -> None:
    for label, color in (("Calma", GREEN), ("Normal", YELLOW), ("Alta", RED)):
        sheet.conditional_format(
            1,
            column,
            rows,
            column,
            {
                "type": "cell",
                "criteria": "==",
                "value": f'"{label}"',
                "format": workbook.add_format({"bg_color": color}),
            },
        )


def _color_signs(workbook: Workbook, sheet: Worksheet, column: int, rows: int) -> None:
    for criteria, color in ((">", GREEN_TEXT), ("<", RED_TEXT)):
        sheet.conditional_format(
            1,
            column,
            rows,
            column,
            {
                "type": "cell",
                "criteria": criteria,
                "value": 0,
                "format": workbook.add_format({"font_color": color}),
            },
        )


# --- gráficos ---


def _write_charts(
    workbook: Workbook, data: ReportData, sheets: list[tuple[str, pd.DataFrame]]
) -> None:
    """Aba Gráficos: por ativo, preço com médias móveis e volatilidade ao longo do tempo."""
    frames = dict(sheets)
    sheet: Worksheet = workbook.add_worksheet("Gráficos")
    indicators, regimes = frames["Indicadores"], frames["Regimes"]
    columns = {name: number for number, name in enumerate(indicators.columns)}
    regime_columns = {name: number for number, name in enumerate(regimes.columns)}

    for index, symbol in enumerate(data.assets.symbols):
        base = symbol.removesuffix(f"-{data.assets.quote}")
        # Ativo sem nenhum dia na janela: fica sem gráfico em vez de derrubar a planilha.
        if not (indicators["Ativo"] == base).any():
            continue
        first, last = _block(indicators, base)
        r_first, r_last = _block(regimes, base)

        price = workbook.add_chart({"type": "line"})
        for column, title, color in (
            ("Fechamento (R$)", "Fechamento", "#1F3864"),
            ("Média 20 dias", "Média 20", "#ED7D31"),
            ("Média 50 dias", "Média 50", "#70AD47"),
            ("Média 200 dias", "Média 200", "#7F7F7F"),
        ):
            price.add_series(
                {
                    "name": title,
                    "categories": ["Indicadores", first, columns["Data"], last, columns["Data"]],
                    "values": ["Indicadores", first, columns[column], last, columns[column]],
                    "line": {
                        "color": color,
                        "width": 1.75 if column == "Fechamento (R$)" else 1.25,
                    },
                }
            )
        _style(price, f"{base}: preço e médias móveis", "R$ #,##0")

        volatility = workbook.add_chart({"type": "line"})
        volatility.add_series(
            {
                "name": "Volatilidade diária",
                "categories": [
                    "Regimes",
                    r_first,
                    regime_columns["Data"],
                    r_last,
                    regime_columns["Data"],
                ],
                "values": [
                    "Regimes",
                    r_first,
                    regime_columns["Volatilidade diária"],
                    r_last,
                    regime_columns["Volatilidade diária"],
                ],
                "line": {"color": "#C00000", "width": 1.5},
            }
        )
        _style(volatility, f"{base}: volatilidade diária", "0.0%")

        row = index * 20
        sheet.insert_chart(row, 0, price)
        sheet.insert_chart(row, 10, volatility)


def _block(frame: pd.DataFrame, base: str) -> tuple[int, int]:
    """Primeira e última linha (0 = cabeçalho) de um ativo numa tabela ordenada por ativo."""
    positions = frame.index[frame["Ativo"] == base]
    return int(positions.min()) + 1, int(positions.max()) + 1


def _style(chart: Chart, title: str, value_format: str) -> None:
    chart.set_title({"name": title})
    chart.set_x_axis(
        {"date_axis": True, "num_format": "mmm/yy", "major_unit": 2, "major_unit_type": "months"}
    )
    chart.set_y_axis(
        {
            "num_format": value_format,
            "major_gridlines": {"visible": True, "line": {"color": "#D9D9D9"}},
        }
    )
    chart.set_legend({"position": "bottom"})
    chart.set_size({"width": 700, "height": 360})
