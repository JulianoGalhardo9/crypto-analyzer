import logging
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session, sessionmaker

from crypto_analyzer.config import QualityConfig
from crypto_analyzer.infra.repositories import (
    load_bronze_responses,
    replace_quality_issues,
    upsert_silver_candles,
)
from crypto_analyzer.pipeline.quality import check_quality
from crypto_analyzer.pipeline.silver import build_silver

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProcessSummary:
    symbol: str
    candles: int
    partial: int
    issues_by_check: dict[str, int]


def process_silver(
    session_factory: sessionmaker[Session],
    symbols: Sequence[str],
    resolution: str,
    now: datetime,
    config: QualityConfig,
) -> list[ProcessSummary]:
    """Bronze -> silver + qualidade, par a par.

    Idempotente: reprocessar atualiza os candles (upsert) e troca os problemas do par,
    sem duplicar nada. Cada par é uma transação: se um falhar, os outros já estão salvos.
    """
    summaries = []
    for symbol in symbols:
        with session_factory() as session:
            responses = load_bronze_responses(session, symbol, resolution)
            silver = build_silver(responses, resolution, now)
            issues = check_quality(
                silver.frame,
                resolution,
                now,
                config,
                duplicates_removed=silver.duplicates_removed,
            )
            upsert_silver_candles(session, symbol, resolution, silver.frame)
            replace_quality_issues(session, symbol, resolution, issues)
            session.commit()

        summary = ProcessSummary(
            symbol=symbol,
            candles=len(silver.frame),
            partial=int(silver.frame["is_partial"].sum()),
            issues_by_check=dict(Counter(issue.check for issue in issues)),
        )
        logger.info("silver: %s %s processado", symbol, resolution)
        summaries.append(summary)
    return summaries
