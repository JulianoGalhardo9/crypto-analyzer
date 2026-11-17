from types import SimpleNamespace

import pytest

from crypto_analyzer.infra import telegram
from crypto_analyzer.interfaces.airflow_callbacks import failure_message, notify_task_failure


def context(map_index: int = -1) -> dict[str, object]:
    ti = SimpleNamespace(
        dag_id="daily_pipeline", task_id="ingest", map_index=map_index, try_number=4
    )
    return {"ti": ti, "run_id": "scheduled__2026-11-17", "exception": ValueError("HTTP 403")}


def test_message_says_which_task_failed_and_why() -> None:
    text = failure_message(context())

    assert "daily_pipeline → ingest" in text
    assert "scheduled__2026-11-17" in text and "tentativa 4" in text
    assert "HTTP 403" in text
    assert "[" not in text.splitlines()[0]  # tarefa sem mapeamento não mostra índice


def test_mapped_task_shows_its_index() -> None:
    assert "daily_pipeline → ingest [2]" in failure_message(context(map_index=2))


def test_callback_never_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(text: str) -> bool:
        raise telegram.TelegramError("o Telegram respondeu HTTP 500")

    monkeypatch.setattr(telegram, "notify", broken)

    notify_task_failure(context())  # não pode levantar
