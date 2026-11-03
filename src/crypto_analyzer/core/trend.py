from crypto_analyzer.core.models import Trend


def classify_trend(close: float, sma_50: float | None, sma_200: float | None) -> Trend | None:
    """Tendência pelo alinhamento do preço com as médias de 50 e 200 dias.

    Subindo: preço > média 50 > média 200. Caindo: preço < média 50 < média 200.
    Qualquer outra ordem é "de lado" (sinais misturados). Sem a média de 200 dias
    (histórico curto), não há conclusão confiável: devolve `None`.
    """
    if sma_50 is None or sma_200 is None:
        return None
    if close > sma_50 > sma_200:
        return Trend.UP
    if close < sma_50 < sma_200:
        return Trend.DOWN
    return Trend.SIDEWAYS
