from collections.abc import Sequence
from typing import Any

import pandas as pd
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from crypto_analyzer.infra.tables import BronzeCandlesRaw, QualityIssueRow, SilverCandle
from crypto_analyzer.pipeline.market_data import RawCandles
from crypto_analyzer.pipeline.quality import QualityIssue
from crypto_analyzer.pipeline.silver import BronzeResponse


def save_raw_candles(session: Session, raw: RawCandles) -> int:
    """Insere a resposta bruta na bronze e devolve o id. Quem chama faz o commit."""
    row = BronzeCandlesRaw(
        symbol=raw.symbol,
        resolution=raw.resolution,
        request_params=dict(raw.params),
        payload=raw.payload,
        fetched_at=raw.fetched_at,
    )
    session.add(row)
    session.flush()  # força o INSERT agora para o id existir
    return row.id


def load_bronze_responses(session: Session, symbol: str, resolution: str) -> list[BronzeResponse]:
    rows = session.scalars(
        select(BronzeCandlesRaw)
        .where(BronzeCandlesRaw.symbol == symbol, BronzeCandlesRaw.resolution == resolution)
        .order_by(BronzeCandlesRaw.fetched_at)
    )
    return [BronzeResponse(row.id, row.fetched_at, row.payload) for row in rows]


def upsert_silver_candles(
    session: Session, symbol: str, resolution: str, frame: pd.DataFrame
) -> None:
    """Grava os candles; se (par, resolução, ts) já existe, atualiza. Reexecutar não duplica."""
    if frame.empty:
        return
    records: list[dict[str, Any]] = [
        {"symbol": symbol, "resolution": resolution, **{str(k): v for k, v in record.items()}}
        for record in frame.reset_index().to_dict("records")
    ]
    statement = insert(SilverCandle)
    # `excluded` é o valor que tentamos inserir; o Postgres o usa quando há conflito de chave.
    update_columns: dict[str, Any] = {
        column: statement.excluded[column] for column in frame.columns
    }
    update_columns["updated_at"] = func.now()
    session.execute(
        statement.on_conflict_do_update(
            index_elements=["symbol", "resolution", "ts"], set_=update_columns
        ),
        records,
    )


def replace_quality_issues(
    session: Session, symbol: str, resolution: str, issues: Sequence[QualityIssue]
) -> None:
    """Troca os problemas antigos do par pelos novos, na mesma transação."""
    session.execute(
        delete(QualityIssueRow).where(
            QualityIssueRow.symbol == symbol, QualityIssueRow.resolution == resolution
        )
    )
    session.add_all(
        QualityIssueRow(
            symbol=symbol,
            resolution=resolution,
            check_name=issue.check,
            severity=issue.severity,
            ts_start=issue.ts_start,
            ts_end=issue.ts_end,
            detail=issue.detail,
        )
        for issue in issues
    )
