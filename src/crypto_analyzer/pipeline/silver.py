from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pandas as pd

# Duração de cada candle; usada para saber se o candle já fechou e para achar buracos.
STEP = {"1h": pd.Timedelta(hours=1), "1d": pd.Timedelta(days=1)}

PRICE_COLUMNS = ["open", "high", "low", "close"]
COLUMNS = [*PRICE_COLUMNS, "volume", "is_partial", "source_bronze_id"]
# A API devolve listas paralelas: t (início), o, h, l, c, v.
PAYLOAD_KEYS = {"t": "ts", "o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"}


@dataclass(frozen=True)
class BronzeResponse:
    """Uma resposta da bronze, com o que a silver precisa para escolher entre duplicatas."""

    bronze_id: int
    fetched_at: datetime
    payload: Mapping[str, Any]


@dataclass(frozen=True)
class SilverCandles:
    frame: pd.DataFrame
    duplicates_removed: int


def parse_payload(payload: Mapping[str, Any]) -> pd.DataFrame:
    """Converte as listas paralelas da API em um DataFrame indexado por `ts` (UTC).

    Os preços chegam como texto ("541.77000000"); aqui viram float64 de verdade.
    """
    missing = PAYLOAD_KEYS.keys() - payload.keys()
    if missing:
        raise ValueError(f"payload inválido, faltam as chaves: {sorted(missing)}")
    if len({len(payload[key]) for key in PAYLOAD_KEYS}) != 1:
        raise ValueError("payload inválido: as listas têm tamanhos diferentes")

    index = pd.DatetimeIndex(pd.to_datetime(payload["t"], unit="s", utc=True), name="ts")
    return pd.DataFrame(
        {
            name: pd.to_numeric(pd.Series(payload[key], dtype="object"), errors="raise").to_numpy(
                dtype="float64"
            )
            for key, name in PAYLOAD_KEYS.items()
            if key != "t"
        },
        index=index,
    )


def build_silver(
    responses: Sequence[BronzeResponse], resolution: str, now: datetime
) -> SilverCandles:
    """Junta várias respostas da bronze em um único conjunto limpo de candles.

    - o mesmo `ts` pode vir em várias respostas; vale o da resposta mais recente
      (ex.: o candle "de hoje" vem incompleto numa coleta e completo na seguinte);
    - `is_partial` marca candles que ainda não fecharam em `now`;
    - `source_bronze_id` guarda de qual resposta cada candle veio (rastreabilidade).
    """
    parts: list[pd.DataFrame] = []
    for response in sorted(responses, key=lambda r: r.fetched_at):
        part = parse_payload(response.payload)
        part["source_bronze_id"] = response.bronze_id
        parts.append(part)

    if not parts:
        return SilverCandles(_empty_frame(), duplicates_removed=0)

    combined = pd.concat(parts)
    # keep="last": como as respostas estão em ordem cronológica, a mais nova ganha.
    is_duplicate = combined.index.duplicated(keep="last")
    frame = combined.loc[~is_duplicate].sort_index()
    frame["is_partial"] = (frame.index + STEP[resolution]) > pd.Timestamp(now)
    return SilverCandles(frame[COLUMNS], duplicates_removed=int(is_duplicate.sum()))


def _empty_frame() -> pd.DataFrame:
    frame = pd.DataFrame(
        {
            **{column: pd.Series(dtype="float64") for column in [*PRICE_COLUMNS, "volume"]},
            "is_partial": pd.Series(dtype="bool"),
            "source_bronze_id": pd.Series(dtype="int64"),
        }
    )
    frame.index = pd.DatetimeIndex([], tz="UTC", name="ts")
    return frame[COLUMNS]
