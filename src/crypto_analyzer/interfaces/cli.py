import asyncio
import logging
from datetime import UTC, datetime

import typer

from crypto_analyzer.config import Settings, load_assets
from crypto_analyzer.infra.db import make_engine, make_session_factory
from crypto_analyzer.infra.mercado_bitcoin import MercadoBitcoinClient
from crypto_analyzer.pipeline.bronze import ingest_candles

app = typer.Typer(help="Análise simples de BTC, ETH e SOL.", no_args_is_help=True)

RESOLUCOES = ("1h", "1d")


@app.callback()
def main() -> None:
    """Mantém `coletar` como subcomando (com um único comando o Typer o esconderia)."""


@app.command()
def coletar(
    resolucao: str = typer.Option("1d", help="Resolução dos candles: 1d ou 1h."),
    candles: int = typer.Option(
        100_000, help="Quantos candles pedir (o máximo traz todo o histórico)."
    ),
) -> None:
    """Coleta os candles da API e grava a resposta crua na bronze."""
    if resolucao not in RESOLUCOES:
        raise typer.BadParameter(
            f"use uma destas: {', '.join(RESOLUCOES)}", param_hint="--resolucao"
        )
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    session_factory = make_session_factory(make_engine(Settings().database_url))  # type: ignore[call-arg]
    symbols = load_assets().symbols

    async def run() -> dict[str, int]:
        async with MercadoBitcoinClient() as client:
            return await ingest_candles(
                client, session_factory, symbols, resolucao, to=datetime.now(UTC), countback=candles
            )

    saved = asyncio.run(run())
    typer.echo(f"Pronto: {len(saved)} respostas gravadas na bronze ({resolucao}).")
