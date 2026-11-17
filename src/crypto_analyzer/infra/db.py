from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from crypto_analyzer.config import Settings


def make_engine(database_url: str) -> Engine:
    # pool_pre_ping descarta conexões mortas (ex.: o Postgres reiniciou) antes de usá-las.
    return create_engine(database_url, pool_pre_ping=True)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)


def session_factory_from_settings() -> sessionmaker[Session]:
    """Sessões do banco do projeto, a partir de DATABASE_URL (ambiente ou `.env`)."""
    return make_session_factory(make_engine(Settings().database_url))  # type: ignore[call-arg]
