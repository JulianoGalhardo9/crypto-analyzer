import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer

from crypto_analyzer.config import (
    load_assets,
    load_quality_config,
    load_regime_config,
    load_report_config,
)
from crypto_analyzer.core.explainer import explain, explain_details, unsupported_asset_message
from crypto_analyzer.infra.db import session_factory_from_settings
from crypto_analyzer.pipeline.bronze import collect_candles
from crypto_analyzer.pipeline.build_analysis import NoDataError, build_analysis
from crypto_analyzer.pipeline.build_report import build_report_data
from crypto_analyzer.pipeline.market_data import MarketDataError
from crypto_analyzer.pipeline.process import process_silver
from crypto_analyzer.pipeline.process_gold import process_gold
from crypto_analyzer.reports.excel import default_report_path, write_report

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

    session_factory = session_factory_from_settings()
    try:
        saved = collect_candles(
            session_factory,
            load_assets().symbols,
            resolucao,
            to=datetime.now(UTC),
            countback=candles,
        )
    except MarketDataError as error:
        typer.echo(
            f"Não consegui coletar: {error}.\n"
            "O que já tinha sido gravado foi mantido. Tente de novo mais tarde."
        )
        raise typer.Exit(code=1) from None
    typer.echo(f"Pronto: {len(saved)} respostas gravadas na bronze ({resolucao}).")


@app.command()
def processar(
    resolucao: str = typer.Option("1d", help="Resolução dos candles: 1d ou 1h."),
) -> None:
    """Transforma a bronze em silver (candles limpos) e roda as checagens de qualidade."""
    if resolucao not in RESOLUCOES:
        raise typer.BadParameter(
            f"use uma destas: {', '.join(RESOLUCOES)}", param_hint="--resolucao"
        )
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    session_factory = session_factory_from_settings()
    summaries = process_silver(
        session_factory, load_assets().symbols, resolucao, datetime.now(UTC), load_quality_config()
    )
    for summary in summaries:
        issues = (
            ", ".join(f"{k}={v}" for k, v in sorted(summary.issues_by_check.items())) or "nenhum"
        )
        typer.echo(
            f"{summary.symbol}: {summary.candles} candles "
            f"({summary.partial} parcial) | problemas: {issues}"
        )


@app.command()
def calcular() -> None:
    """Calcula indicadores e regimes (gold) a partir da silver e grava no banco."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    session_factory = session_factory_from_settings()
    try:
        summaries = process_gold(session_factory, load_assets(), load_regime_config())
    except ValueError as error:
        raise typer.BadParameter(str(error)) from error
    for summary in summaries:
        typer.echo(
            f"{summary.symbol}: {summary.days} dias | "
            f"{summary.indicator_rows_with_data} com média de 200 dias | "
            f"regime atual: {summary.latest_regime or 'sem histórico suficiente'}"
        )


@app.command()
def analisar(
    ativo: str = typer.Argument(..., help="BTC, ETH ou SOL."),
    detalhes: bool = typer.Option(False, "--detalhes", help="Mostra os números por trás."),
) -> None:
    """Explica em linguagem simples como está um ativo."""
    assets = load_assets()
    base = ativo.upper().removesuffix(f"-{assets.quote}")
    # A checagem do ativo vem antes de qualquer acesso ao banco.
    if base not in {asset.symbol for asset in assets.assets}:
        typer.echo(unsupported_asset_message())
        raise typer.Exit(code=1)

    session_factory = session_factory_from_settings()
    try:
        analysis = build_analysis(
            session_factory,
            assets,
            base,
            datetime.now(UTC),
            load_quality_config(),
            load_regime_config(),
        )
    except NoDataError:
        typer.echo(
            f"Ainda não tenho dados de {base}. Rode, nesta ordem: "
            "crypto-analyzer coletar, processar e calcular."
        )
        raise typer.Exit(code=1) from None
    typer.echo(explain_details(analysis) if detalhes else explain(analysis))


@app.command()
def planilha(
    pasta: Annotated[Path, typer.Option(help="Pasta onde o .xlsx é salvo.")] = Path("output"),
) -> None:
    """Gera a planilha Excel com a análise completa dos ativos."""
    session_factory = session_factory_from_settings()
    now = datetime.now(UTC)
    try:
        data = build_report_data(
            session_factory,
            load_assets(),
            now,
            load_quality_config(),
            load_regime_config(),
            load_report_config(),
        )
    except NoDataError as error:
        typer.echo(
            f"Não dá para gerar a planilha: {error}. Rode, nesta ordem: "
            "crypto-analyzer coletar, processar e calcular."
        )
        raise typer.Exit(code=1) from None
    path = write_report(data, default_report_path(pasta, now))
    typer.echo(f"Planilha gerada: {path}")
