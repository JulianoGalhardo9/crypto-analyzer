import logging
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy.orm import Session, sessionmaker

from crypto_analyzer.infra.repositories import save_raw_candles
from crypto_analyzer.pipeline.market_data import MarketDataClient

logger = logging.getLogger(__name__)


async def ingest_candles(
    client: MarketDataClient,
    session_factory: sessionmaker[Session],
    symbols: Sequence[str],
    resolution: str,
    *,
    to: datetime,
    countback: int,
) -> dict[str, int]:
    """Busca os candles de cada par e grava a resposta crua na bronze.

    Devolve `{par: id da linha gravada}`. O commit é feito por par: se um falhar,
    o erro sobe, mas o que já foi gravado fica (e o Airflow poderá repetir só o que faltou).
    As chamadas são sequenciais de propósito, por causa do limite de 1 requisição por segundo.
    """
    saved: dict[str, int] = {}
    for symbol in symbols:
        raw = await client.fetch_candles(symbol, resolution, to=to, countback=countback)
        with session_factory() as session:
            saved[symbol] = save_raw_candles(session, raw)
            session.commit()
        logger.info("bronze: %s %s gravado (id=%d)", symbol, resolution, saved[symbol])
    return saved
