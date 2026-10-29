from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Numeric, String, func
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


class SilverCandle(Base):
    """Camada silver: um candle limpo por (par, resolução, instante UTC)."""

    __tablename__ = "silver_candles"

    # A chave composta é o que permite o upsert: reprocessar o mesmo candle o substitui.
    symbol: Mapped[str] = mapped_column(String(20), primary_key=True)
    resolution: Mapped[str] = mapped_column(String(5), primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    open: Mapped[Decimal] = mapped_column(Numeric(24, 8))
    high: Mapped[Decimal] = mapped_column(Numeric(24, 8))
    low: Mapped[Decimal] = mapped_column(Numeric(24, 8))
    close: Mapped[Decimal] = mapped_column(Numeric(24, 8))
    volume: Mapped[Decimal] = mapped_column(Numeric(24, 8))
    is_partial: Mapped[bool] = mapped_column(Boolean)
    source_bronze_id: Mapped[int] = mapped_column(ForeignKey("bronze_candles_raw.id"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class QualityIssueRow(Base):
    """Problemas achados pelas checagens; reescritos a cada processamento do par."""

    __tablename__ = "quality_issues"
    __table_args__ = (Index("ix_quality_issues_lookup", "symbol", "resolution"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20))
    resolution: Mapped[str] = mapped_column(String(5))
    # `check` é palavra reservada do SQL, por isso o nome da coluna é check_name.
    check_name: Mapped[str] = mapped_column(String(30))
    severity: Mapped[str] = mapped_column(String(10))
    ts_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ts_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    detail: Mapped[str] = mapped_column(String(300))
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
