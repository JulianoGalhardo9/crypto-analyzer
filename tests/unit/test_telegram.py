import json

import httpx
import pytest

from crypto_analyzer.config import Settings
from crypto_analyzer.infra.telegram import MAX_LENGTH, TelegramError, notify, send_message

TOKEN = "123456:SEGREDO-DE-TESTE"


def client_for(handler: httpx.MockTransport) -> httpx.Client:
    return httpx.Client(transport=handler)


def test_sends_the_text_to_the_chat() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"ok": True, "result": {}})

    send_message("olá", token=TOKEN, chat_id="42", client=client_for(httpx.MockTransport(handler)))

    [request] = requests
    assert request.url.path == f"/bot{TOKEN}/sendMessage"
    assert json.loads(request.content) == {"chat_id": "42", "text": "olá"}


def test_long_messages_are_cut_to_the_telegram_limit() -> None:
    sent: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content)["text"])
        return httpx.Response(200, json={"ok": True})

    send_message(
        "x" * 5000, token=TOKEN, chat_id="42", client=client_for(httpx.MockTransport(handler))
    )

    assert len(sent[0]) == MAX_LENGTH


def test_rejection_is_explained_without_leaking_the_token() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"ok": False, "description": "Unauthorized"})

    with pytest.raises(TelegramError) as error:
        send_message(
            "oi", token=TOKEN, chat_id="42", client=client_for(httpx.MockTransport(handler))
        )

    assert "HTTP 401" in str(error.value) and "Unauthorized" in str(error.value)
    assert TOKEN not in str(error.value)


def test_network_error_does_not_leak_the_token() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"não conectou em {request.url}")

    with pytest.raises(TelegramError) as error:
        send_message(
            "oi", token=TOKEN, chat_id="42", client=client_for(httpx.MockTransport(handler))
        )

    assert TOKEN not in str(error.value)
    assert error.value.__cause__ is None and error.value.__suppress_context__


def test_without_configuration_the_alert_only_goes_to_the_log(
    caplog: pytest.LogCaptureFixture,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("não deveria chamar o Telegram")

    settings = Settings(database_url="postgresql://x", telegram_bot_token="", telegram_chat_id="")

    with caplog.at_level("WARNING"):
        sent = notify("regime mudou", settings, client_for(httpx.MockTransport(handler)))

    assert sent is False
    assert "regime mudou" in caplog.text


def test_configured_notify_sends() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    settings = Settings(
        database_url="postgresql://x", telegram_bot_token=TOKEN, telegram_chat_id="42"
    )

    assert notify("oi", settings, client_for(httpx.MockTransport(handler))) is True
