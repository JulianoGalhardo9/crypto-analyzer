from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class Regime(StrEnum):
    """Quão agitado está o preço em relação ao histórico recente do próprio ativo."""

    CALM = "calm"
    NORMAL = "normal"
    HIGH = "high"


@dataclass(frozen=True)
class RegimeChange:
    """Troca do regime confirmado (com histerese) de um ativo, no dia em que se confirmou."""

    ts: datetime
    previous: Regime
    current: Regime


class Trend(StrEnum):
    """Direção do preço nas últimas semanas, a partir das médias móveis."""

    UP = "up"
    SIDEWAYS = "sideways"
    DOWN = "down"


class CorrelationLevel(StrEnum):
    """Correlação de hoje com o BTC comparada ao histórico da própria correlação."""

    BELOW_USUAL = "below"
    USUAL = "usual"
    ABOVE_USUAL = "above"


class Signal(StrEnum):
    """Sinais avaliados (decisão do autor, 2026-11-17): os que estão por trás da resposta."""

    RSI_ABOVE_HIGH = "rsi_above_70"
    RSI_BELOW_LOW = "rsi_below_30"
    CROSS_ABOVE_SMA_200 = "cross_above_sma_200"
    CROSS_BELOW_SMA_200 = "cross_below_sma_200"


@dataclass(frozen=True)
class BacktestResult:
    signal: Signal
    horizon_days: int
    raw_count: int  # dias com o sinal, contando os sobrepostos
    independent_count: int  # ocorrências independentes
    evaluated_count: int  # independentes com o preço do fim do horizonte disponível
    enough_sample: bool
    # Só preenchidos com amostra suficiente:
    mean_return: float | None
    median_return: float | None
    hit_rate: float | None  # fração das ocorrências em que o preço subiu
    # Linha de base: qualquer dia com o mesmo horizonte.
    baseline_mean: float | None
    baseline_hit_rate: float | None
    first_event: datetime | None
    last_event: datetime | None


@dataclass(frozen=True)
class Analysis:
    """Todos os números de um ativo num dia. `None` = ainda sem dados suficientes."""

    symbol: str  # par da API, ex.: SOL-BRL
    base: str  # ex.: SOL
    name: str  # ex.: Solana
    article: str  # "o" ou "a": o BTC, a SOL
    is_benchmark: bool  # True para o BTC (a correlação com ele mesmo não se aplica)
    as_of: datetime  # início do último candle fechado (UTC)
    last_candle_ts: datetime  # início do candle mais recente, inclusive o parcial
    data_age_hours: float
    is_stale: bool
    price: float
    change_1d: float | None  # frações: 0.032 = +3,2%
    change_7d: float | None
    change_30d: float | None
    trend: Trend | None
    sma_20: float | None
    sma_50: float | None
    sma_200: float | None
    rsi_14: float | None
    macd: float | None
    macd_signal: float | None
    macd_histogram: float | None
    atr_14: float | None
    bb_lower: float | None
    bb_middle: float | None
    bb_upper: float | None
    volatility: float | None  # desvio padrão dos retornos diários (30 dias)
    volatility_percentile: float | None
    regime: Regime | None  # já com histerese
    raw_regime: Regime | None
    corr_btc_90: float | None
    corr_percentile: float | None
    corr_level: CorrelationLevel | None
    typical_daily_move: float | None  # mediana do |retorno diário| no último ano
    big_daily_move: float | None  # percentil 90 do |retorno diário| no último ano
    support_30: float | None
    resistance_30: float | None
    support_90: float | None
    resistance_90: float | None
    # Backtest dos sinais (vazio se ainda não calculado) e a amostra mínima usada no cálculo.
    backtests: tuple[BacktestResult, ...] = ()
    backtest_min_sample: int | None = None
