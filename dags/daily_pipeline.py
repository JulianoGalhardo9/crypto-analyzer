"""Pipeline diária: API -> bronze -> silver (+ qualidade) -> gold -> alerta de mudança de regime.

Fina de propósito: cada tarefa chama uma função de `crypto_analyzer` que também roda pelo CLI
(`coletar`, `processar`, `calcular`). Aqui só se define a ordem, o paralelismo e as falhas.
"""

from datetime import UTC, datetime, timedelta

from airflow.sdk import Asset, dag, task

from crypto_analyzer.interfaces.airflow_callbacks import GOLD_ASSET_URI, notify_task_failure

RESOLUTION = "1d"
# Dias de candles pedidos em cada coleta: cobre dias em que a coleta falhou.
# A bronze guarda a resposta inteira e a silver remove as repetições.
COUNTBACK_DAYS = 30
GOLD = Asset(name="crypto_gold", uri=GOLD_ASSET_URI)


@dag(
    # 00:15 UTC: o candle diário fecha às 00:00 UTC; a folga dá tempo para a API consolidá-lo.
    schedule="15 0 * * *",
    start_date=datetime(2026, 11, 1, tzinfo=UTC),
    catchup=False,
    max_active_runs=1,
    default_args={
        "retries": 3,
        "retry_delay": timedelta(minutes=5),
        # No Airflow 3.4 é um multiplicador (não mais True/False): 5, 10, 20 minutos.
        "retry_exponential_backoff": 2.0,
        "execution_timeout": timedelta(minutes=10),
        "on_failure_callback": notify_task_failure,
    },
    tags=["crypto-analyzer"],
)
def daily_pipeline() -> None:
    @task
    def list_symbols() -> list[str]:
        """Os pares vêm do config/assets.yaml na hora da execução, não na leitura do arquivo."""
        from crypto_analyzer.config import load_assets

        return load_assets().symbols

    # Uma instância por ativo, mas uma de cada vez: a API aceita 1 requisição por segundo.
    @task(max_active_tis_per_dagrun=1)
    def ingest(symbol: str, *, data_interval_end: datetime | None = None) -> int:
        """API -> bronze. Devolve o id da resposta gravada (XCom pequeno)."""
        from crypto_analyzer.infra.db import session_factory_from_settings
        from crypto_analyzer.pipeline.bronze import collect_candles

        # Agendada: o horário da execução; num backfill, o dia refeito; manual: agora.
        to = data_interval_end or datetime.now(UTC)
        saved = collect_candles(
            session_factory_from_settings(), [symbol], RESOLUTION, to=to, countback=COUNTBACK_DAYS
        )
        return saved[symbol]

    # Sem limite: cada ativo é independente e só usa o banco.
    @task
    def silver(symbol: str) -> dict[str, int]:
        """Bronze -> silver + checagens de qualidade. Devolve contagens (XCom pequeno)."""
        from crypto_analyzer.config import load_quality_config
        from crypto_analyzer.infra.db import session_factory_from_settings
        from crypto_analyzer.pipeline.process import process_silver

        [summary] = process_silver(
            session_factory_from_settings(),
            [symbol],
            RESOLUTION,
            datetime.now(UTC),
            load_quality_config(),
        )
        return {"candles": summary.candles, "partial": summary.partial, **summary.issues_by_check}

    # Ao terminar com sucesso, registra um evento do Asset: é o que dispara a daily_report.
    @task(outlets=[GOLD])
    def gold() -> list[str]:
        """Silver -> gold de todos os ativos juntos (a correlação precisa do BTC).

        Devolve os textos de alerta das mudanças de regime novas (pode ser lista vazia).
        """
        from crypto_analyzer.config import load_assets, load_backtest_config, load_regime_config
        from crypto_analyzer.infra.db import session_factory_from_settings
        from crypto_analyzer.pipeline.alerts import regime_alert_messages
        from crypto_analyzer.pipeline.process_gold import process_gold

        assets = load_assets()
        summaries = process_gold(
            session_factory_from_settings(), assets, load_regime_config(), load_backtest_config()
        )
        return regime_alert_messages(summaries, assets)

    @task
    def alert_regime_changes(messages: list[str]) -> int:
        """Separada do gold: se o Telegram falhar, o retry não recalcula nada."""
        from crypto_analyzer.infra.telegram import notify

        for message in messages:
            notify(message)
        return len(messages)

    symbols = list_symbols()
    ingested = ingest.expand(symbol=symbols)
    # Cada etapa mapeada só começa quando TODAS as instâncias da anterior terminam:
    # assim o gold sempre vê a silver do BTC já atualizada.
    cleaned = silver.expand(symbol=symbols)
    ingested >> cleaned
    messages = gold()
    cleaned >> messages
    alert_regime_changes(messages)


daily_pipeline()
