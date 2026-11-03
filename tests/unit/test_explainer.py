import dataclasses
from datetime import UTC, datetime
from itertools import product

import pytest

from crypto_analyzer.core.explainer import (
    DISCLAIMER,
    explain,
    explain_details,
    unsupported_asset_message,
)
from crypto_analyzer.core.models import Analysis, CorrelationLevel, Regime, Trend


def make_analysis(**overrides: object) -> Analysis:
    base = Analysis(
        symbol="SOL-BRL",
        base="SOL",
        name="Solana",
        article="a",
        is_benchmark=False,
        as_of=datetime(2026, 10, 28, tzinfo=UTC),
        last_candle_ts=datetime(2026, 10, 29, tzinfo=UTC),
        data_age_hours=20.0,
        is_stale=False,
        price=548.46,
        change_1d=0.032,
        change_7d=0.08,
        change_30d=-0.04,
        trend=Trend.UP,
        sma_20=520.0,
        sma_50=500.0,
        sma_200=450.0,
        rsi_14=55.0,
        macd=3.1,
        macd_signal=2.2,
        macd_histogram=0.9,
        atr_14=26.45,
        bb_lower=490.0,
        bb_middle=520.0,
        bb_upper=550.0,
        volatility=0.0216,
        volatility_percentile=88.0,
        regime=Regime.HIGH,
        raw_regime=Regime.HIGH,
        corr_btc_90=0.83,
        corr_percentile=50.0,
        corr_level=CorrelationLevel.USUAL,
        typical_daily_move=0.018,
        big_daily_move=0.045,
        support_30=480.0,
        resistance_30=560.0,
        support_90=430.0,
        resistance_90=600.0,
    )
    return dataclasses.replace(base, **overrides)  # type: ignore[arg-type]


def info_lines(text: str) -> list[str]:
    """As linhas de informação são as que começam com emoji, antes de 'O que isso significa'."""
    return [line for line in text.split("\n\n")[1].splitlines() if line.strip()]


# --- o exemplo do CLAUDE.md ---


def test_high_agitation_uptrend_reads_like_the_spec_example() -> None:
    text = explain(make_analysis())

    assert text.startswith("SOL (Solana) está em alta, mas agitada.")
    assert "📈 Tendência:    subindo nas últimas semanas" in text
    assert "🌊 Agitação:     ALTA (o preço está oscilando mais que o normal para a SOL)" in text
    assert "🕐 Último dia:   +3,2% (dia fechado em 28/10)" in text
    assert "O que isso significa:" in text
    assert text.rstrip().endswith(DISCLAIMER)


def test_typical_moves_come_from_the_data_not_from_a_template() -> None:
    text = explain(make_analysis(typical_daily_move=0.021, big_daily_move=0.067))

    assert "cerca de 2,1% por dia" in text
    assert "mais de 6,7%" in text


# --- regras do CLAUDE.md valem em qualquer combinação ---

TRENDS = [Trend.UP, Trend.SIDEWAYS, Trend.DOWN, None]
REGIMES = [Regime.CALM, Regime.NORMAL, Regime.HIGH, None]
LEVELS = [*CorrelationLevel, None]


@pytest.mark.parametrize(("trend", "regime", "level"), list(product(TRENDS, REGIMES, LEVELS)))
def test_rules_hold_for_every_combination(
    trend: Trend | None, regime: Regime | None, level: CorrelationLevel | None
) -> None:
    analysis = make_analysis(trend=trend, regime=regime, corr_level=level, rsi_14=75.0)

    for text in (explain(analysis), explain_details(analysis)):
        lowered = text.lower()
        assert DISCLAIMER in text  # sempre o aviso
        for forbidden in ("compre", "comprar", "venda", "vender", "sugerimos", "recomendamos"):
            assert forbidden not in lowered
        assert "nan" not in lowered.replace("financeira", "")  # nenhum NaN vazando
    assert len(info_lines(explain(analysis))) <= 4


def test_never_says_price_will_go_anywhere() -> None:
    for rsi in (80.0, 20.0):
        text = explain(make_analysis(rsi_14=rsi)).lower()
        for prediction in ("vai subir", "vai cair", "deve subir", "deve cair", "tende a reverter"):
            assert prediction not in text


# --- histórico insuficiente e dado velho ---


def test_missing_history_is_said_instead_of_inventing_precision() -> None:
    text = explain(
        make_analysis(trend=None, regime=None, corr_btc_90=None, corr_level=None, rsi_14=None)
    )

    assert "ainda não há histórico suficiente para uma conclusão confiável" in text
    assert "sem histórico suficiente para dizer" in text


def test_stale_data_gets_a_visible_warning_with_the_age() -> None:
    days = explain(make_analysis(is_stale=True, data_age_hours=5 * 24))
    hours = explain(make_analysis(is_stale=True, data_age_hours=30))

    assert "os dados mais recentes são de 5 dias atrás" in days
    assert "são de 30 horas atrás" in hours
    assert "atrás" not in explain(make_analysis(is_stale=False))


# --- RSI ---


def test_rsi_is_mentioned_only_at_the_extremes_and_explained() -> None:
    assert "RSI" not in explain(make_analysis(rsi_14=55.0))
    high = explain(make_analysis(rsi_14=74.0))
    low = explain(make_analysis(rsi_14=26.0))

    assert "subiu muito rápido" in high and "mede a velocidade das altas e quedas" in high
    assert "caiu muito rápido" in low


# --- BTC e correlação ---


def test_btc_has_no_correlation_line() -> None:
    text = explain(
        make_analysis(base="BTC", name="Bitcoin", article="o", is_benchmark=True, corr_btc_90=None)
    )

    assert "Com o BTC" not in text
    assert "não se aplica" in explain_details(
        make_analysis(is_benchmark=True, corr_btc_90=None, corr_level=None)
    )


@pytest.mark.parametrize(
    ("corr", "expected"),
    [
        (0.83, "anda junto (quando o BTC cai, a SOL costuma cair também)"),
        (0.55, "anda parcialmente junto"),
        (0.10, "se move de forma independente"),
        (-0.60, "tende a andar no sentido oposto"),
    ],
)
def test_correlation_wording(corr: float, expected: str) -> None:
    assert expected in explain(make_analysis(corr_btc_90=corr, corr_level=None))


def test_correlation_says_if_today_is_tighter_or_looser_than_usual() -> None:
    above = explain(make_analysis(corr_level=CorrelationLevel.ABOVE_USUAL))
    below = explain(make_analysis(corr_level=CorrelationLevel.BELOW_USUAL))

    assert "hoje mais colada que o normal" in above
    assert "hoje menos colada que o normal" in below


# --- detalhes e mensagens ---


def test_details_show_the_numbers_behind_the_answer() -> None:
    text = explain_details(make_analysis())

    for expected in (
        "R$ 548,46",
        "+3,2% / +8,0% / -4,0%",
        "R$ 520,00 / R$ 500,00 / R$ 450,00",
        "RSI de 14 dias: 55,0",
        "ATR de 14 dias: R$ 26,45 (4,8% do preço",
        "correlação: 0,83",
        "30 dias: R$ 480,00 — R$ 560,00",
        "Backtest dos sinais: ainda não disponível.",
    ):
        assert expected in text


def test_thousands_use_dot_and_decimals_use_comma() -> None:
    assert "R$ 435.668,00" in explain_details(make_analysis(price=435668.0))


def test_unsupported_asset_message_is_friendly() -> None:
    assert unsupported_asset_message() == "Por enquanto acompanho apenas BTC, ETH e SOL."


def test_text_agrees_with_the_gender_of_each_asset() -> None:
    sol = explain(make_analysis(regime=Regime.CALM))  # a SOL
    eth = explain(
        make_analysis(base="ETH", name="Ethereum", article="o", regime=Regime.CALM)
    )  # o ETH

    assert "ETH (Ethereum) está em alta, e bem calmo." in eth
    assert "para o ETH" in eth and "o BTC cai, o ETH costuma cair" in eth
    assert "SOL (Solana) está em alta, e bem calma." in sol
    assert "para a SOL" in sol and "a SOL costuma cair" in sol
    assert "último ano do ETH" in explain_details(
        make_analysis(base="ETH", name="Ethereum", article="o")
    )
    assert "último ano da SOL" in explain_details(make_analysis())
