"""Planilha Excel automática, gerada sempre que o gold é atualizado.

Agendamento orientado a dados: em vez de um horário, a DAG espera um evento do Asset do gold,
emitido pela tarefa `gold` da daily_pipeline. Se a pipeline atrasar ou falhar, a planilha não
é gerada com dados velhos.
"""

from datetime import UTC, datetime, timedelta

from airflow.sdk import Asset, dag, task

from crypto_analyzer.interfaces.airflow_callbacks import GOLD_ASSET_URI, notify_task_failure

GOLD = Asset(name="crypto_gold", uri=GOLD_ASSET_URI)


@dag(
    schedule=[GOLD],
    start_date=datetime(2026, 11, 1, tzinfo=UTC),
    catchup=False,
    max_active_runs=1,
    default_args={
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
        "execution_timeout": timedelta(minutes=10),
        "on_failure_callback": notify_task_failure,
    },
    tags=["crypto-analyzer"],
)
def daily_report() -> None:
    @task
    def build_spreadsheet() -> str:
        """Lê o banco e grava `crypto_report_AAAA-MM-DD.xlsx`; devolve o caminho (XCom pequeno)."""
        from crypto_analyzer.config import (
            Settings,
            load_assets,
            load_quality_config,
            load_regime_config,
            load_report_config,
        )
        from crypto_analyzer.infra.db import session_factory_from_settings
        from crypto_analyzer.pipeline.build_report import build_report_data
        from crypto_analyzer.reports.excel import default_report_path, write_report

        now = datetime.now(UTC)
        data = build_report_data(
            session_factory_from_settings(),
            load_assets(),
            now,
            load_quality_config(),
            load_regime_config(),
            load_report_config(),
        )
        output_dir = Settings().output_dir  # type: ignore[call-arg]
        # Reexecutar no mesmo dia sobrescreve o arquivo do dia: não acumula cópias.
        return str(write_report(data, default_report_path(output_dir, now)))

    build_spreadsheet()


daily_report()
