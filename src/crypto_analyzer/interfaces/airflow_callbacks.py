"""Peças usadas pelas DAGs, sem importar o Airflow: callbacks e identificadores de Assets."""

import logging
from collections.abc import Mapping
from typing import Any

logger = logging.getLogger(__name__)

# Asset do gold: a daily_pipeline o atualiza e a daily_report roda depois de cada atualização.
# O prefixo "x-" é o recomendado pelo Airflow para identificadores próprios (sem semântica).
GOLD_ASSET_URI = "x-crypto-analyzer://gold"


def failure_message(context: Mapping[str, Any]) -> str:
    """Texto curto dizendo qual tarefa falhou, em qual execução e por quê."""
    ti = context["ti"]
    map_index = getattr(ti, "map_index", -1)
    where = f"{ti.dag_id} → {ti.task_id}" + (f" [{map_index}]" if map_index >= 0 else "")
    return (
        f"❌ Falha no Airflow: {where}\n"
        f"Execução: {context.get('run_id')} (tentativa {ti.try_number})\n"
        f"Erro: {context.get('exception')}"
    )


def notify_task_failure(context: Mapping[str, Any]) -> None:
    """`on_failure_callback`: avisa no Telegram (ou no log). Nunca levanta exceção."""
    # Import tardio: o arquivo da DAG importa este módulo a cada leitura do dag-processor.
    from crypto_analyzer.infra.telegram import notify

    try:
        notify(failure_message(context))
    except Exception:
        # Um erro aqui esconderia a falha original; registra e segue.
        logger.exception("falha ao enviar o alerta de falha")
