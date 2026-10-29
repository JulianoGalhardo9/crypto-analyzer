from enum import StrEnum


class Regime(StrEnum):
    """Quão agitado está o preço em relação ao histórico recente do próprio ativo."""

    CALM = "calm"
    NORMAL = "normal"
    HIGH = "high"
