"""Números -> texto simples em português. Função pura: nada de I/O, nada de cálculo novo.

Regras (ver CLAUDE.md): sem jargão sem explicar, nunca mandar comprar ou vender, nunca
prever preço, e dizer quando falta histórico ou o dado está velho em vez de fingir precisão.
"""

from crypto_analyzer.core.models import Analysis, CorrelationLevel, Regime, Trend

DISCLAIMER = "⚠️ Informativo, não é recomendação de investimento."

# Limites clássicos do RSI (Wilder): acima de 70 subiu rápido demais; abaixo de 30, caiu.
RSI_HIGH = 70
RSI_LOW = 30
# Leitura usual da força da correlação em estatística. Para estes ativos a correlação com o
# BTC é sempre alta (medido), por isso o texto também diz como ela está em relação ao normal.
CORR_STRONG = 0.7
CORR_MODERATE = 0.4

LABEL_WIDTH = 16


def explain(analysis: Analysis) -> str:
    """Resposta padrão: 4 linhas de informação e uma explicação curta."""
    lines = [
        _headline(analysis),
        "",
        _line("📈", "Tendência:", _trend_text(analysis)),
        _line("🌊", "Agitação:", _agitation_text(analysis)),
    ]
    if not analysis.is_benchmark:
        lines.append(_line("🔗", "Com o BTC:", _correlation_text(analysis)))
    lines.append(_line("🕐", "Último dia:", _last_day_text(analysis)))
    lines += ["", "O que isso significa:", _meaning(analysis), "", DISCLAIMER]
    return "\n".join(lines)


def explain_details(analysis: Analysis) -> str:
    """Resposta com os números técnicos por trás (`--detalhes`)."""
    a = analysis
    rows = [
        f"{a.base} ({a.name}) — números em {a.as_of:%d/%m/%Y} (UTC), último dia fechado",
        "",
        "Preço e variação",
        f"  Preço (fechamento): {_money(a.price)}",
        f"  Variação 1d / 7d / 30d: {_pct(a.change_1d)} / {_pct(a.change_7d)} / "
        f"{_pct(a.change_30d)}",
        "",
        "Tendência (médias móveis: média do preço nos últimos N dias)",
        f"  Média de 20 / 50 / 200 dias: {_money(a.sma_20)} / {_money(a.sma_50)} / "
        f"{_money(a.sma_200)}",
        f"  Leitura: {_trend_text(a)}",
        "",
        "Velocidade do preço",
        f"  RSI de 14 dias: {_num(a.rsi_14, 1)} (acima de {RSI_HIGH}: subiu rápido; "
        f"abaixo de {RSI_LOW}: caiu rápido)",
        f"  MACD / sinal / histograma: {_num(a.macd)} / {_num(a.macd_signal)} / "
        f"{_num(a.macd_histogram)}",
        "",
        "Oscilação",
        f"  ATR de 14 dias: {_money(a.atr_14)} ({_atr_share(a)} do preço, por dia)",
        f"  Bandas de Bollinger (20 dias): {_money(a.bb_lower)} — {_money(a.bb_middle)} — "
        f"{_money(a.bb_upper)}",
        f"  Volatilidade diária (30 dias): {_pct(a.volatility, signed=False)}",
        f"  Percentil da volatilidade (vs. último ano {_of(a)}): "
        f"{_num(a.volatility_percentile, 0)}",
        f"  Agitação: {_regime_name(a.regime)} (leitura do dia, sem a confirmação: "
        f"{_regime_name(a.raw_regime)})",
        "",
        "Correlação com o BTC (90 dias)",
        f"  {_correlation_numbers(a)}",
        "",
        "Referências de preço (mínima e máxima recentes)",
        f"  30 dias: {_money(a.support_30)} — {_money(a.resistance_30)}",
        f"  90 dias: {_money(a.support_90)} — {_money(a.resistance_90)}",
        "",
        "Backtest dos sinais: ainda não disponível.",
        "",
        DISCLAIMER,
    ]
    return "\n".join(rows)


def unsupported_asset_message() -> str:
    return "Por enquanto acompanho apenas BTC, ETH e SOL."


# --- partes da resposta simples ---


def _headline(a: Analysis) -> str:
    trend = {
        Trend.UP: "em alta",
        Trend.SIDEWAYS: "andando de lado",
        Trend.DOWN: "em queda",
        None: None,
    }[a.trend]
    feminine = a.article == "a"
    agitation = {
        Regime.CALM: "bem calma" if feminine else "bem calmo",
        Regime.NORMAL: "com agitação normal",
        Regime.HIGH: "agitada" if feminine else "agitado",
        None: None,
    }[a.regime]
    who = f"{a.base} ({a.name})"
    if trend is None or agitation is None:
        return f"{who}: ainda não há histórico suficiente para uma conclusão confiável."
    connector = "mas" if a.regime is Regime.HIGH else "e"
    return f"{who} está {trend}, {connector} {agitation}."


def _the(a: Analysis) -> str:
    """Artigo + ativo: "a SOL", "o BTC"."""
    return f"{a.article} {a.base}"


def _of(a: Analysis) -> str:
    """De + artigo + ativo: "da SOL", "do BTC"."""
    return f"d{a.article} {a.base}"


def _line(emoji: str, label: str, text: str) -> str:
    return f"{emoji} {label:<{LABEL_WIDTH - 2}}{text}"


def _trend_text(a: Analysis) -> str:
    return {
        Trend.UP: "subindo nas últimas semanas",
        Trend.SIDEWAYS: "de lado, sem uma direção clara",
        Trend.DOWN: "caindo nas últimas semanas",
        None: "sem histórico suficiente para dizer",
    }[a.trend]


def _agitation_text(a: Analysis) -> str:
    return {
        Regime.HIGH: f"ALTA (o preço está oscilando mais que o normal para {_the(a)})",
        Regime.NORMAL: f"NORMAL (oscilando como de costume para {_the(a)})",
        Regime.CALM: f"CALMA (oscilando menos que o normal para {_the(a)})",
        None: "sem histórico suficiente para dizer",
    }[a.regime]


def _correlation_text(a: Analysis) -> str:
    if a.corr_btc_90 is None:
        return "sem histórico suficiente para dizer"
    if a.corr_btc_90 >= CORR_STRONG:
        text = f"anda junto (quando o BTC cai, {_the(a)} costuma cair também)"
    elif a.corr_btc_90 >= CORR_MODERATE:
        text = "anda parcialmente junto"
    elif a.corr_btc_90 > -CORR_MODERATE:
        text = "se move de forma independente"
    else:
        text = "tende a andar no sentido oposto"
    usual = {
        CorrelationLevel.ABOVE_USUAL: "; hoje mais colada que o normal",
        CorrelationLevel.BELOW_USUAL: "; hoje menos colada que o normal",
        CorrelationLevel.USUAL: "",
        None: "",
    }[a.corr_level]
    return text + usual


def _last_day_text(a: Analysis) -> str:
    return f"{_pct(a.change_1d)} (dia fechado em {a.as_of:%d/%m})"


def _meaning(a: Analysis) -> str:
    sentences = []
    sentences.append(
        {
            Trend.UP: "O preço vem subindo nas últimas semanas.",
            Trend.SIDEWAYS: "O preço está andando de lado, sem uma direção clara.",
            Trend.DOWN: "O preço vem caindo nas últimas semanas.",
            None: "Ainda não há histórico suficiente para dizer a tendência.",
        }[a.trend]
    )
    sentences.append(
        {
            Regime.HIGH: f"A agitação está acima do normal para {_the(a)}, "
            "com movimentos mais bruscos que de costume.",
            Regime.NORMAL: f"A agitação está dentro do normal para {_the(a)}.",
            Regime.CALM: f"As oscilações estão menores que o normal para {_the(a)}.",
            None: "Ainda não há histórico suficiente para classificar a agitação.",
        }[a.regime]
    )
    if a.typical_daily_move is not None and a.big_daily_move is not None:
        sentences.append(
            f"No último ano, {_the(a)} costumou variar cerca de "
            f"{_pct(a.typical_daily_move, signed=False)} por dia e, em 1 de cada 10 dias, "
            f"mais de {_pct(a.big_daily_move, signed=False)}."
        )
    if a.rsi_14 is not None and a.rsi_14 >= RSI_HIGH:
        sentences.append(
            "Nos últimos dias o preço subiu muito rápido "
            f"(o RSI, que mede a velocidade das altas e quedas, está em {_num(a.rsi_14, 0)})."
        )
    elif a.rsi_14 is not None and a.rsi_14 <= RSI_LOW:
        sentences.append(
            "Nos últimos dias o preço caiu muito rápido "
            f"(o RSI, que mede a velocidade das altas e quedas, está em {_num(a.rsi_14, 0)})."
        )
    if a.is_stale:
        sentences.append(
            f"⏳ Atenção: os dados mais recentes são de {_age_text(a.data_age_hours)} atrás, "
            "então o quadro pode ter mudado."
        )
    return " ".join(sentences)


# --- formatação em português (vírgula decimal, ponto de milhar) ---


def _swap_separators(text: str) -> str:
    return text.replace(",", "§").replace(".", ",").replace("§", ".")


def _pct(value: float | None, signed: bool = True) -> str:
    if value is None:
        return "—"
    return _swap_separators(f"{value * 100:{'+' if signed else ''},.1f}%")


def _money(value: float | None) -> str:
    if value is None:
        return "—"
    return "R$ " + _swap_separators(f"{value:,.2f}")


def _num(value: float | None, decimals: int = 2) -> str:
    if value is None:
        return "—"
    return _swap_separators(f"{value:,.{decimals}f}")


def _atr_share(a: Analysis) -> str:
    if a.atr_14 is None:
        return "—"
    return _pct(a.atr_14 / a.price, signed=False)


def _regime_name(regime: Regime | None) -> str:
    return {
        Regime.CALM: "calma",
        Regime.NORMAL: "normal",
        Regime.HIGH: "alta",
        None: "sem histórico suficiente",
    }[regime]


def _correlation_numbers(a: Analysis) -> str:
    if a.is_benchmark:
        return "não se aplica (o BTC é a referência)"
    return (
        f"correlação: {_num(a.corr_btc_90)} (de -1 a 1); "
        f"percentil no último ano {_of(a)}: {_num(a.corr_percentile, 0)}"
    )


def _age_text(hours: float) -> str:
    if hours < 48:
        return f"{hours:.0f} horas"
    return f"{hours / 24:.0f} dias"
