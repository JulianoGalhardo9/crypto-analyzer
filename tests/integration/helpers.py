from datetime import UTC, datetime

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from crypto_analyzer.config import AssetInfo, AssetsConfig
from crypto_analyzer.infra.repositories import save_raw_candles, upsert_silver_candles
from crypto_analyzer.pipeline.market_data import RawCandles

ASSETS = AssetsConfig(
    quote="BRL",
    benchmark="BTC",
    assets=[
        AssetInfo(symbol="BTC", name="Bitcoin", article="o"),
        AssetInfo(symbol="SOL", name="Solana", article="a"),
    ],
)
DAYS = 400
FIRST_DAY = "2025-09-01"


def seed_silver(session: Session, symbol: str, seed: int) -> None:
    """Grava DAYS candles sintéticos; o último é marcado como parcial (dia em andamento)."""
    bronze_id = save_raw_candles(
        session,
        RawCandles(symbol, "1d", {}, {"t": []}, datetime(2026, 10, 28, tzinfo=UTC)),
    )
    rng = np.random.default_rng(seed)
    index = pd.date_range(FIRST_DAY, periods=DAYS, freq="D", tz="UTC", name="ts")
    close = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.02, DAYS))), index=index)
    frame = pd.DataFrame(
        {
            "open": close,
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "volume": 1.0,
            "is_partial": [False] * (DAYS - 1) + [True],
            "source_bronze_id": bronze_id,
        }
    )
    upsert_silver_candles(session, symbol, "1d", frame)
    session.commit()
