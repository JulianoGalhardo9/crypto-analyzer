from sqlalchemy.orm import Session

from crypto_analyzer.infra.tables import BronzeCandlesRaw
from crypto_analyzer.pipeline.market_data import RawCandles


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
