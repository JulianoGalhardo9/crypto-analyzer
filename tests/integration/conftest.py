from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, delete
from sqlalchemy.orm import Session

from crypto_analyzer.config import Settings
from crypto_analyzer.infra.db import make_engine
from crypto_analyzer.infra.tables import BronzeCandlesRaw

ROOT = Path(__file__).parent.parent.parent


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    """Engine do Postgres do Docker, com as migrations já aplicadas."""
    command.upgrade(Config(str(ROOT / "alembic.ini")), "head")
    engine = make_engine(Settings().database_url)  # type: ignore[call-arg]
    yield engine
    engine.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    """Sessão com a bronze limpa, para cada teste começar do zero."""
    with Session(engine, expire_on_commit=False) as session:
        session.execute(delete(BronzeCandlesRaw))
        session.commit()
        yield session
