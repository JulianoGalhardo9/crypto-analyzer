import re
from pathlib import Path
from types import TracebackType

import pytest
from typer.testing import CliRunner

from crypto_analyzer.interfaces import cli
from crypto_analyzer.interfaces.cli import app
from crypto_analyzer.pipeline.build_analysis import NoDataError
from crypto_analyzer.pipeline.market_data import MarketDataError
from tests.unit.report_data import build_report_data

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

    # Com FORCE_COLOR (como no CI) a ajuda vem com códigos ANSI que partem o texto; tiramos antes.
    plain = re.sub(r"\x1b\[[0-9;]*m", "", result.output)
    assert result.exit_code == 0
    assert "--detalhes" in plain


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


def test_planilha_without_gold_explains_what_to_run(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def no_data(*args: object) -> None:
        raise NoDataError("ainda não há dados calculados de BTC")

    monkeypatch.setattr(cli, "build_report_data", no_data)

    result = runner.invoke(app, ["planilha", "--pasta", str(tmp_path)])

    assert result.exit_code == 1
    assert "coletar, processar e calcular" in result.output
    assert not list(tmp_path.iterdir())  # nenhum arquivo pela metade


def test_planilha_writes_the_dated_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(cli, "build_report_data", lambda *args: build_report_data())

    result = runner.invoke(app, ["planilha", "--pasta", str(tmp_path)])

    assert result.exit_code == 0
    [report] = tmp_path.iterdir()
    assert re.fullmatch(r"crypto_report_\d{4}-\d{2}-\d{2}\.xlsx", report.name)
    assert report.name in result.output.replace("\n", "")
