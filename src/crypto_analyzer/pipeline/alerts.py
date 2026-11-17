from collections.abc import Sequence

from crypto_analyzer.config import AssetsConfig
from crypto_analyzer.core.explainer import regime_change_message
from crypto_analyzer.pipeline.process_gold import GoldSummary


def regime_alert_messages(summaries: Sequence[GoldSummary], assets: AssetsConfig) -> list[str]:
    """Um texto de alerta por mudança nova de regime, na ordem dos ativos e das datas."""
    by_symbol = {f"{asset.symbol}-{assets.quote}": asset for asset in assets.assets}
    return [
        regime_change_message(
            by_symbol[summary.symbol].symbol,
            by_symbol[summary.symbol].name,
            by_symbol[summary.symbol].article,
            change,
        )
        for summary in summaries
        for change in summary.new_changes
    ]
