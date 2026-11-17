from datetime import UTC, datetime

from crypto_analyzer.core.models import Regime, RegimeChange
from crypto_analyzer.pipeline.alerts import regime_alert_messages
from crypto_analyzer.pipeline.process_gold import GoldSummary
from tests.unit.report_data import ASSETS


def summary(symbol: str, *changes: RegimeChange) -> GoldSummary:
    return GoldSummary(symbol, 100, 100, "calm", list(changes))


def test_one_message_per_new_change_with_the_asset_name() -> None:
    sol_change = RegimeChange(datetime(2026, 11, 16, tzinfo=UTC), Regime.CALM, Regime.HIGH)

    messages = regime_alert_messages([summary("BTC-BRL"), summary("SOL-BRL", sol_change)], ASSETS)

    assert len(messages) == 1
    assert messages[0].startswith("🔔 A SOL (Solana) mudou de agitação: calma → alta.")


def test_no_changes_no_messages() -> None:
    assert regime_alert_messages([summary("BTC-BRL"), summary("SOL-BRL")], ASSETS) == []
