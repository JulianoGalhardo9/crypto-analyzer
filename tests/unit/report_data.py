"""Dados sintéticos compartilhados pelos testes da planilha."""

from datetime import UTC, datetime

import numpy as np
import pandas as pd

from crypto_analyzer.config import AssetInfo, AssetsConfig, RegimeConfig
from crypto_analyzer.core.backtest import run_backtest
from crypto_analyzer.core.models import Analysis, CorrelationLevel, Regime, Trend
from crypto_analyzer.pipeline.gold import GoldFrames, compute_gold
from crypto_analyzer.reports.frames import QualityRecord, ReportData

ASSETS = AssetsConfig(
    quote="BRL",
    benchmark="BTC",
    assets=[
        AssetInfo(symbol="BTC", name="Bitcoin", article="o"),
        AssetInfo(symbol="SOL", name="Solana", article="a"),
    ],
)
REGIME = RegimeConfig(
    volatility_window=10,
    percentile_window=100,
    min_history=40,
    calm_below=33,
    high_above=66,
    confirm_days=3,
    refresh_hours={"calm": 6, "normal": 3, "high": 1},
)
DAYS = 600
WINDOW = 365
NOW = datetime(2026, 10, 29, 12, tzinfo=UTC)
LAST_DAY = "2026-10-28"


def make_candles(seed: int, days: int = DAYS) -> pd.DataFrame:
    """Como nos dados reais: os ativos começam em datas diferentes e terminam no mesmo dia."""
    rng = np.random.default_rng(seed)
    index = pd.date_range(end=LAST_DAY, periods=days, freq="D", tz="UTC", name="ts")
    close = pd.Series(100 * np.exp(np.cumsum(rng.normal(0.001, 0.02, days))), index=index)
    return pd.DataFrame(
        {"open": close, "high": close * 1.01, "low": close * 0.99, "close": close, "volume": 5.0}
    )


def make_analysis(base: str, name: str, **overrides: object) -> Analysis:
    values: dict[str, object] = {
        "symbol": f"{base}-BRL",
        "base": base,
        "name": name,
        "article": "o",
        "is_benchmark": base == "BTC",
        "as_of": datetime(2026, 10, 28, tzinfo=UTC),
        "last_candle_ts": datetime(2026, 10, 29, tzinfo=UTC),
        "data_age_hours": 12.0,
        "is_stale": False,
        "price": 435668.0,
        "change_1d": 0.005,
        "change_7d": -0.02,
        "change_30d": 0.1,
        "trend": Trend.UP,
        "sma_20": 1.0,
        "sma_50": 1.0,
        "sma_200": 1.0,
        "rsi_14": 60.1,
        "macd": 1.0,
        "macd_signal": 1.0,
        "macd_histogram": 0.0,
        "atr_14": 1.0,
        "bb_lower": 1.0,
        "bb_middle": 1.0,
        "bb_upper": 1.0,
        "volatility": 0.017,
        "volatility_percentile": 31.0,
        "regime": Regime.CALM,
        "raw_regime": Regime.CALM,
        "corr_btc_90": None if base == "BTC" else 0.83,
        "corr_percentile": None if base == "BTC" else 50.0,
        "corr_level": None if base == "BTC" else CorrelationLevel.USUAL,
        "typical_daily_move": 0.01,
        "big_daily_move": 0.03,
        "support_30": 1.0,
        "resistance_30": 2.0,
        "support_90": 1.0,
        "resistance_90": 2.0,
    }
    values.update(overrides)
    return Analysis(**values)  # type: ignore[arg-type]


# Amostra mínima baixa de propósito: os dados sintéticos têm poucos sinais e o teste precisa
# de resultados dos dois tipos (com e sem amostra suficiente).
MIN_SAMPLE = 5


def backtest_fields(candles: pd.DataFrame, gold: GoldFrames) -> dict[str, object]:
    results = run_backtest(
        candles["close"], gold.indicators["rsi_14"], gold.indicators["sma_200"], [7, 30], MIN_SAMPLE
    )
    return {"backtests": tuple(results), "backtest_min_sample": MIN_SAMPLE}


def build_report_data() -> ReportData:
    candles = {"BTC-BRL": make_candles(1), "SOL-BRL": make_candles(2, 700)}
    gold = compute_gold(candles, "BTC-BRL", REGIME)
    return ReportData(
        assets=ASSETS,
        candles=candles,
        indicators={symbol: frames.indicators for symbol, frames in gold.items()},
        regimes={symbol: frames.regimes for symbol, frames in gold.items()},
        quality=[
            QualityRecord(
                "SOL-BRL",
                "outlier",
                "info",
                datetime(2022, 11, 9, tzinfo=UTC),
                datetime(2022, 11, 9, tzinfo=UTC),
                "movimento extremo de -42,4%",
            ),
            QualityRecord("BTC-BRL", "duplicate", "info", None, None, "3 candles repetidos"),
        ],
        analyses=[
            make_analysis("BTC", "Bitcoin", **backtest_fields(candles["BTC-BRL"], gold["BTC-BRL"])),
            make_analysis(
                "SOL", "Solana", article="a", **backtest_fields(candles["SOL-BRL"], gold["SOL-BRL"])
            ),
        ],
        generated_at=NOW,
        window_days=WINDOW,
    )
