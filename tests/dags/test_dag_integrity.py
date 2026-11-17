"""As DAGs carregam sem erro e têm a forma combinada (retries, callbacks, agendamento)."""

from datetime import timedelta
from pathlib import Path

import pytest
from airflow.dag_processing.dagbag import DagBag

from crypto_analyzer.interfaces.airflow_callbacks import GOLD_ASSET_URI, notify_task_failure

DAGS_FOLDER = Path(__file__).parent.parent.parent / "dags"


@pytest.fixture(scope="module")
def dagbag() -> DagBag:
    # Os exemplos do Airflow ficam de fora pelo AIRFLOW__CORE__LOAD_EXAMPLES do conftest.
    return DagBag(dag_folder=str(DAGS_FOLDER))


def test_every_dag_imports_without_errors(dagbag: DagBag) -> None:
    assert dagbag.import_errors == {}


def test_expected_dags_exist(dagbag: DagBag) -> None:
    assert set(dagbag.dag_ids) == {"daily_pipeline", "daily_report", "intraday_refresh"}


def test_every_task_retries_and_alerts_on_failure(dagbag: DagBag) -> None:
    for dag in dagbag.dags.values():
        for task in dag.tasks:
            assert task.retries >= 1, task.task_id
            assert task.retry_delay == timedelta(minutes=5), task.task_id
            # O Airflow guarda o callback como foi passado: uma função ou uma lista delas.
            callbacks = task.on_failure_callback
            callbacks = callbacks if isinstance(callbacks, list) else [callbacks]
            assert notify_task_failure in callbacks, task.task_id


def test_daily_pipeline_shape(dagbag: DagBag) -> None:
    dag = dagbag.dags["daily_pipeline"]

    assert dag.catchup is False and dag.max_active_runs == 1
    assert {t.task_id for t in dag.tasks} == {
        "list_symbols",
        "ingest",
        "silver",
        "gold",
        "alert_regime_changes",
    }
    # ordem: coleta de todos -> silver de todos -> gold -> alerta
    assert dag.get_task("ingest").downstream_task_ids == {"silver"}
    assert dag.get_task("silver").downstream_task_ids == {"gold"}
    assert dag.get_task("gold").downstream_task_ids == {"alert_regime_changes"}


def test_ingestion_runs_one_asset_at_a_time(dagbag: DagBag) -> None:
    """A API aceita 1 requisição por segundo; a silver pode rodar em paralelo."""
    dag = dagbag.dags["daily_pipeline"]

    assert dag.get_task("ingest").max_active_tis_per_dagrun == 1
    assert dag.get_task("silver").max_active_tis_per_dagrun is None


def test_report_runs_after_each_gold_update(dagbag: DagBag) -> None:
    """Agendamento por dados: a tarefa gold emite o Asset que dispara a daily_report."""
    [outlet] = dagbag.dags["daily_pipeline"].get_task("gold").outlets
    assert outlet.uri == GOLD_ASSET_URI

    timetable = dagbag.dags["daily_report"].timetable
    assert timetable.asset_triggered
    assert [asset.uri for asset in timetable.asset_condition.objects] == [GOLD_ASSET_URI]


def test_intraday_refresh_checks_every_hour_and_short_circuits(dagbag: DagBag) -> None:
    dag = dagbag.dags["intraday_refresh"]

    assert dag.timetable.expression == "5 * * * *"
    assert dag.catchup is False and dag.max_active_runs == 1
    decision = dag.get_task("due_symbols")
    # A decisão é um short-circuit: lista vazia pula a atualização.
    assert "ShortCircuit" in type(decision).__name__
    assert decision.downstream_task_ids == {"refresh"}
    assert dag.get_task("refresh").max_active_tis_per_dagrun == 1
