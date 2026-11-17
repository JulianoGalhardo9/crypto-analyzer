import pandas as pd
import pytest

from crypto_analyzer.reports.frames import (
    DISCLAIMER,
    ReportData,
    about_frame,
    candles_frame,
    indicators_frame,
    quality_frame,
    regime_changes_frame,
    regimes_frame,
    summary_frame,
)
from tests.unit.report_data import ASSETS, NOW, WINDOW, build_report_data, make_analysis


@pytest.fixture
def data() -> ReportData:
    return build_report_data()


def is_sorted_by_asset_then_date(frame: pd.DataFrame) -> bool:
    order = {"BTC": 0, "SOL": 1}
    keys = list(zip(frame["Ativo"].map(order), frame["Data"], strict=True))
    return keys == sorted(keys)


# --- abas diárias ---


@pytest.mark.parametrize("builder", [candles_frame, indicators_frame, regimes_frame])
def test_daily_sheets_have_the_window_per_asset_in_order(data: ReportData, builder: object) -> None:
    frame = builder(data)  # type: ignore[operator]

    assert frame.groupby("Ativo").size().to_dict() == {"BTC": WINDOW, "SOL": WINDOW}
    assert is_sorted_by_asset_then_date(frame)
    assert frame.columns[:2].tolist() == ["Ativo", "Data"]


@pytest.mark.parametrize("builder", [candles_frame, indicators_frame, regimes_frame])
def test_dates_are_real_dates_without_timezone(data: ReportData, builder: object) -> None:
    frame = builder(data)  # type: ignore[operator]

    assert str(frame["Data"].dtype) == "datetime64[ns]" or str(frame["Data"].dtype).startswith(
        "datetime64"
    )
    assert frame["Data"].dt.tz is None


def test_candles_sheet_has_numeric_columns_and_matches_the_source(data: ReportData) -> None:
    frame = candles_frame(data)

    expected = [
        "Ativo",
        "Data",
        "Abertura (R$)",
        "Máxima (R$)",
        "Mínima (R$)",
        "Fechamento (R$)",
        "Volume",
    ]
    assert frame.columns.tolist() == expected
    numeric = frame.drop(columns=["Ativo", "Data"])
    assert (numeric.dtypes == "float64").all()
    assert not frame.isna().any().any()
    last_btc = frame[frame["Ativo"] == "BTC"].iloc[-1]
    assert last_btc["Fechamento (R$)"] == pytest.approx(data.candles["BTC-BRL"]["close"].iloc[-1])


def test_indicators_sheet_has_every_indicator_and_only_expected_blanks(
    data: ReportData,
) -> None:
    frame = indicators_frame(data)

    assert "Média 200 dias" in frame.columns and "Correlação com o BTC (90 dias)" in frame.columns
    blanks = frame.isna().sum()
    assert blanks.drop("Correlação com o BTC (90 dias)").eq(0).all()  # janela já aquecida
    corr = frame.groupby("Ativo")["Correlação com o BTC (90 dias)"].apply(lambda s: s.isna().all())
    assert corr.to_dict() == {"BTC": True, "SOL": False}  # só o BTC não tem


def test_regimes_sheet_translates_labels_to_portuguese(data: ReportData) -> None:
    frame = regimes_frame(data)

    labels = set(frame["Agitação confirmada"].dropna()) | set(frame["Agitação do dia"].dropna())
    assert labels and labels <= {"Calma", "Normal", "Alta"}  # nenhum "calm"/"high" em inglês


# --- mudanças de regime ---


def test_regime_changes_by_hand() -> None:
    index = pd.date_range("2026-01-01", periods=8, freq="D", tz="UTC")
    labels = ["calm", "calm", "calm", "normal", "normal", "high", "high", "high"]
    regimes = pd.DataFrame({"regime": pd.Series(labels, index=index, dtype="string")})
    data = ReportData(
        assets=ASSETS,
        candles={},
        indicators={},
        regimes={"BTC-BRL": regimes},
        quality=[],
        analyses=[],
        generated_at=NOW,
        window_days=WINDOW,
    )

    frame = regime_changes_frame(data)

    assert frame.to_dict("records") == [
        {
            "Ativo": "BTC",
            "Data": pd.Timestamp("2026-01-04"),
            "Regime anterior": "Calma",
            "Novo regime": "Normal",
            "Dias no regime anterior": 3,
        },
        {
            "Ativo": "BTC",
            "Data": pd.Timestamp("2026-01-06"),
            "Regime anterior": "Normal",
            "Novo regime": "Alta",
            "Dias no regime anterior": 2,
        },
    ]


def test_regime_changes_ignore_the_warmup_and_use_the_whole_history(data: ReportData) -> None:
    frame = regime_changes_frame(data)

    assert frame.columns.tolist() == [
        "Ativo",
        "Data",
        "Regime anterior",
        "Novo regime",
        "Dias no regime anterior",
    ]
    assert (frame["Regime anterior"] != frame["Novo regime"]).all()
    assert (frame["Dias no regime anterior"] >= 1).all()
    assert not frame.isna().any().any()


# --- resumo, qualidade e sobre ---


def test_summary_has_one_row_per_asset_with_numbers_and_portuguese_labels(
    data: ReportData,
) -> None:
    frame = summary_frame(data)

    assert frame["Ativo"].tolist() == ["BTC", "SOL"]
    assert frame["Tendência"].tolist() == ["Subindo", "Subindo"]
    assert frame["Agitação"].tolist() == ["Calma", "Calma"]
    assert frame["Preço (R$)"].dtype == "float64"
    assert frame["Variação 1 dia"].iloc[0] == pytest.approx(0.005)
    assert pd.isna(frame["Correlação com o BTC (90 dias)"].iloc[0])  # o BTC não tem
    assert frame["Correlação com o BTC (90 dias)"].iloc[1] == pytest.approx(0.83)
    assert frame["Último dia fechado"].iloc[0] == pd.Timestamp("2026-10-28")


def test_summary_says_when_there_is_not_enough_history() -> None:
    data = ReportData(
        assets=ASSETS,
        candles={},
        indicators={},
        regimes={},
        quality=[],
        analyses=[make_analysis("SOL", "Solana", trend=None, regime=None)],
        generated_at=NOW,
        window_days=WINDOW,
    )

    frame = summary_frame(data)

    assert frame["Tendência"].iloc[0] == "Sem histórico"
    assert frame["Agitação"].iloc[0] == "Sem histórico"


def test_quality_sheet_translates_and_keeps_real_dates(data: ReportData) -> None:
    frame = quality_frame(data)

    assert frame.columns.tolist() == [
        "Ativo",
        "Verificação",
        "Gravidade",
        "Início",
        "Fim",
        "Detalhe",
    ]
    assert frame["Ativo"].tolist() == ["BTC", "SOL"]
    assert frame["Verificação"].tolist() == ["Candles repetidos", "Movimento extremo"]
    assert set(frame["Gravidade"]) == {"Informativo"}
    assert pd.isna(frame["Início"].iloc[0])  # a duplicata não tem data
    assert frame["Início"].iloc[1] == pd.Timestamp("2022-11-09")


def test_quality_sheet_with_no_issues_is_just_the_header() -> None:
    data = ReportData(
        assets=ASSETS,
        candles={},
        indicators={},
        regimes={},
        quality=[],
        analyses=[],
        generated_at=NOW,
        window_days=WINDOW,
    )

    assert quality_frame(data).empty


def test_about_sheet_documents_source_window_and_disclaimer(data: ReportData) -> None:
    frame = about_frame(data)
    values = dict(zip(frame["Campo"], frame["Valor"], strict=True))

    assert values["Gerado em (UTC)"] == pd.Timestamp("2026-10-29 12:00")
    assert "Mercado Bitcoin" in values["Fonte dos dados"]
    assert values["Janela exibida (dias)"] == WINDOW
    assert values["Aviso"] == DISCLAIMER
    assert values["Atualidade dos dados"] == "Dados recentes"


def test_about_sheet_warns_when_data_is_old() -> None:
    stale = make_analysis("SOL", "Solana", is_stale=True, data_age_hours=6 * 24)
    data = ReportData(
        assets=ASSETS,
        candles={},
        indicators={},
        regimes={},
        quality=[],
        analyses=[stale],
        generated_at=NOW,
        window_days=WINDOW,
    )

    values = dict(zip(about_frame(data)["Campo"], about_frame(data)["Valor"], strict=True))

    assert (
        "ATENÇÃO" in values["Atualidade dos dados"] and "6 dias" in values["Atualidade dos dados"]
    )
