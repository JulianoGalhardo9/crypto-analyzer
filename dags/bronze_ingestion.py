"""Primeira DAG: coleta diária dos candles do Mercado Bitcoin para a bronze.

Fina de propósito: toda a lógica está em `crypto_analyzer.pipeline.bronze` e roda igual pelo CLI
(`crypto-analyzer coletar`). Aqui só se define quando rodar e o que fazer se falhar.
"""

from datetime import UTC, datetime, timedelta

from airflow.sdk import dag, task

# Dias de candles pedidos em cada coleta. Mais que 1 para cobrir dias em que a coleta falhou;
# a bronze guarda a resposta inteira e a silver remove as repetições.
COUNTBACK_DAYS = 30


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
    },
    tags=["crypto-analyzer", "bronze"],
)
def bronze_ingestion() -> None:
    @task
    def ingest(*, data_interval_end: datetime | None = None) -> dict[str, int]:
        """Grava na bronze uma resposta por ativo e devolve `{par: id}` (XCom pequeno)."""
        # Imports dentro da tarefa: o dag-processor relê este arquivo a cada 30 s e não
        # precisa carregar pandas/SQLAlchemy só para descobrir a forma da DAG.
        from crypto_analyzer.config import Settings, load_assets
        from crypto_analyzer.infra.db import make_engine, make_session_factory
        from crypto_analyzer.pipeline.bronze import collect_candles

        session_factory = make_session_factory(make_engine(Settings().database_url))  # type: ignore[call-arg]
        # Em execuções agendadas é o horário da execução; num backfill, o dia que está sendo
        # refeito. Sem ele (alguns disparos manuais), vale o momento atual.
        to = data_interval_end or datetime.now(UTC)
        return collect_candles(
            session_factory, load_assets().symbols, "1d", to=to, countback=COUNTBACK_DAYS
        )

    ingest()


bronze_ingestion()
