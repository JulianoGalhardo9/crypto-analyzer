"""Atualização dos candles de 1h, com frequência que depende do regime de cada ativo.

Roda de hora em hora (aos 5 minutos, logo depois de o candle de 1h fechar). A tarefa de decisão
lê o regime e a última coleta de cada ativo; ativos em "alta" atualizam a cada 1h, "normal" a
cada 3h e "calma" a cada 6h (config/regimes.yaml). Mudança de regime não é alertada aqui: o
regime vem do candle diário, e o alerta sai da daily_pipeline.
"""

from datetime import UTC, datetime, timedelta

from airflow.sdk import dag, task

from crypto_analyzer.interfaces.airflow_callbacks import notify_task_failure

# 3 dias de candles de 1h por coleta: cobre o intervalo mais longo (6h) e algumas falhas.
COUNTBACK_HOURS = 72


@dag(
    schedule="5 * * * *",
    start_date=datetime(2026, 11, 1, tzinfo=UTC),
    catchup=False,
    # Se uma execução atrasar, a próxima espera em vez de coletar o mesmo ativo em paralelo.
    max_active_runs=1,
    default_args={
        # Um retry só: a próxima checagem já vem em 1 hora.
        "retries": 1,
        "retry_delay": timedelta(minutes=5),
        "execution_timeout": timedelta(minutes=10),
        "on_failure_callback": notify_task_failure,
    },
    tags=["crypto-analyzer"],
)
def intraday_refresh() -> None:
    # short_circuit: se a lista vier vazia ("nada a fazer nesta hora"), as tarefas seguintes
    # ficam como "skipped" em vez de rodar. Se não vier, a lista vira a entrada do .expand().
    @task.short_circuit
    def due_symbols(*, data_interval_end: datetime | None = None) -> list[str]:
        from crypto_analyzer.config import load_assets, load_regime_config
        from crypto_analyzer.infra.db import session_factory_from_settings
        from crypto_analyzer.pipeline.intraday import symbols_due_for_refresh

        now = data_interval_end or datetime.now(UTC)
        return symbols_due_for_refresh(
            session_factory_from_settings(), load_assets(), now, load_regime_config()
        )

    # Uma por vez: a API aceita 1 requisição por segundo.
    @task(max_active_tis_per_dagrun=1)
    def refresh(symbol: str) -> dict[str, int]:
        from crypto_analyzer.config import load_quality_config
        from crypto_analyzer.infra.db import session_factory_from_settings
        from crypto_analyzer.pipeline.intraday import refresh_hourly

        summary = refresh_hourly(
            session_factory_from_settings(),
            symbol,
            datetime.now(UTC),
            load_quality_config(),
            countback=COUNTBACK_HOURS,
        )
        return {"candles": summary.candles, "partial": summary.partial}

    refresh.expand(symbol=due_symbols())


intraday_refresh()
