from collections.abc import Sequence
from typing import Any

import pandas as pd
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from crypto_analyzer.config import AssetsConfig
from crypto_analyzer.infra.tables import (
    Base,
    BronzeCandlesRaw,
    DimAtivo,
    FactIndicador,
    FactRegime,
    QualityIssueRow,
    SilverCandle,
)
from crypto_analyzer.pipeline.gold import GoldFrames
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


def _upsert_frame(
    session: Session,
    model: type[Base],
    frame: pd.DataFrame,
    key_columns: list[str],
    constants: dict[str, Any],
) -> None:
    """INSERT ... ON CONFLICT DO UPDATE de um DataFrame indexado por `ts`.

    `constants` são colunas com o mesmo valor em todas as linhas (ex.: o par). NaN vira NULL.
    Reexecutar com os mesmos dados não duplica nada: a chave composta decide o que atualizar.
    """
    if frame.empty:
        return
    clean = frame.astype(object).where(frame.notna(), None)
    records: list[dict[str, Any]] = [
        {**constants, **{str(k): v for k, v in record.items()}}
        for record in clean.reset_index().to_dict("records")
    ]
    statement = insert(model)
    # `excluded` é o valor que tentamos inserir; o Postgres o usa quando há conflito de chave.
    update_columns: dict[str, Any] = {
        column: statement.excluded[column] for column in frame.columns
    }
    update_columns["updated_at"] = func.now()
    session.execute(
        statement.on_conflict_do_update(index_elements=key_columns, set_=update_columns),
        records,
    )


def upsert_silver_candles(
    session: Session, symbol: str, resolution: str, frame: pd.DataFrame
) -> None:
    _upsert_frame(
        session,
        SilverCandle,
        frame,
        ["symbol", "resolution", "ts"],
        {"symbol": symbol, "resolution": resolution},
    )


def load_closed_candles(session: Session, symbol: str, resolution: str) -> pd.DataFrame:
    """Candles fechados da silver (sem o parcial), como float64, indexados por `ts` em UTC."""
    rows = session.execute(
        select(
            SilverCandle.ts,
            SilverCandle.open,
            SilverCandle.high,
            SilverCandle.low,
            SilverCandle.close,
            SilverCandle.volume,
        )
        .where(
            SilverCandle.symbol == symbol,
            SilverCandle.resolution == resolution,
            SilverCandle.is_partial.is_(False),
        )
        .order_by(SilverCandle.ts)
    ).all()
    frame = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    return frame.set_index("ts").astype("float64")


def upsert_ativos(session: Session, assets: AssetsConfig) -> dict[str, int]:
    """Garante um registro em dim_ativo por par e devolve `{par: id}`."""
    rows = [
        {
            "symbol": f"{asset.symbol}-{assets.quote}",
            "base": asset.symbol,
            "quote": assets.quote,
            "name": asset.name,
        }
        for asset in assets.assets
    ]
    statement = insert(DimAtivo)
    session.execute(
        statement.on_conflict_do_update(
            index_elements=["symbol"],
            set_={"name": statement.excluded.name},
        ),
        rows,
    )
    return {
        symbol: ativo_id
        for symbol, ativo_id in session.execute(select(DimAtivo.symbol, DimAtivo.id)).all()
    }


def upsert_gold(session: Session, ativo_id: int, frames: GoldFrames) -> None:
    constants = {"ativo_id": ativo_id}
    _upsert_frame(session, FactIndicador, frames.indicators, ["ativo_id", "ts"], constants)
    _upsert_frame(session, FactRegime, frames.regimes, ["ativo_id", "ts"], constants)


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
