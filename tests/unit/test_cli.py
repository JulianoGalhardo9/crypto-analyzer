from types import TracebackType

import pytest
from typer.testing import CliRunner

from crypto_analyzer.interfaces import cli
from crypto_analyzer.interfaces.cli import app
from crypto_analyzer.pipeline.market_data import MarketDataError

runner = CliRunner()


@pytest.mark.parametrize("ticker", ["XRP", "doge", "XRP-BRL"])
def test_unsupported_asset_gets_a_friendly_message_without_touching_the_database(
    ticker: str,
) -> None:
    result = runner.invoke(app, ["analisar", ticker])

    assert result.exit_code == 1
    assert "Por enquanto acompanho apenas BTC, ETH e SOL." in result.output


def test_analisar_is_documented_in_the_help() -> None:
    result = runner.invoke(app, ["analisar", "--help"])

    assert result.exit_code == 0
    assert "--detalhes" in result.output


class DownClient:
    """Fake de MercadoBitcoinClient para uma API fora do ar."""

    async def __aenter__(self) -> "DownClient":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None

    async def fetch_candles(self, *args: object, **kwargs: object) -> None:
        raise MarketDataError("HTTP 302: a API redirecionou em vez de responder")


def test_coletar_explains_a_failing_api_instead_of_dumping_a_traceback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cli, "MercadoBitcoinClient", DownClient)

    result = runner.invoke(app, ["coletar"])

    assert result.exit_code == 1
    assert "Não consegui coletar" in result.output
    assert "Tente de novo mais tarde" in result.output
    assert "Traceback" not in result.output
