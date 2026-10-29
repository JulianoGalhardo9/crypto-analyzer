from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, delete, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from crypto_analyzer.config import Settings
from crypto_analyzer.infra.db import make_engine
from crypto_analyzer.infra.tables import (
    BronzeCandlesRaw,
    DimAtivo,
    FactIndicador,
    FactRegime,
    QualityIssueRow,
    SilverCandle,
)

ROOT = Path(__file__).parent.parent.parent


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    """Engine de um banco SEPARADO só para testes (`<banco>_test`), com as migrations aplicadas.

    Os testes apagam tabelas; por isso nunca podem rodar no banco com os dados reais coletados.
    """
    real_url = make_url(Settings().database_url)  # type: ignore[call-arg]
    test_db = f"{real_url.database}_test"
    test_url = real_url.set(database=test_db)

    admin = create_engine(real_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.scalar(text("select 1 from pg_database where datname = :n"), {"n": test_db})
        if not exists:
            conn.execute(text(f'create database "{test_db}"'))
    admin.dispose()

    # O Alembic lê DATABASE_URL (migrations/env.py); apontamos para o banco de teste só aqui.
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("DATABASE_URL", test_url.render_as_string(hide_password=False))
        command.upgrade(Config(str(ROOT / "alembic.ini")), "head")

    engine = make_engine(test_url.render_as_string(hide_password=False))
    yield engine
    engine.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    """Sessão com todas as tabelas de teste limpas, para cada teste começar do zero."""
    with Session(engine, expire_on_commit=False) as session:
        # Chaves estrangeiras: apaga-se primeiro quem referencia (gold, depois silver).
        session.execute(delete(FactIndicador))
        session.execute(delete(FactRegime))
        session.execute(delete(DimAtivo))
        session.execute(delete(SilverCandle))
        session.execute(delete(QualityIssueRow))
        session.execute(delete(BronzeCandlesRaw))
        session.commit()
        yield session
