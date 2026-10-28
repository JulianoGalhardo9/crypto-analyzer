from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class BronzeCandlesRaw(Base):
    """Camada bronze: cada resposta da API guardada exatamente como chegou.

    Só recebe INSERT; nunca atualizamos nem apagamos linhas (imutável).
    """

    __tablename__ = "bronze_candles_raw"
    __table_args__ = (Index("ix_bronze_candles_raw_lookup", "symbol", "resolution", "fetched_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20))
    resolution: Mapped[str] = mapped_column(String(5))
    request_params: Mapped[dict[str, Any]] = mapped_column(JSONB)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    # Momento em que o cliente recebeu a resposta (UTC).
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # Momento em que o banco gravou a linha; preenchido pelo próprio Postgres.
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
