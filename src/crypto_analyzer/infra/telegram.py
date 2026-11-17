"""Envio de mensagens pelo Bot API do Telegram (só `sendMessage`), com httpx.

O token faz parte da URL; por isso nenhum erro daqui repete a URL ou a mensagem original
do httpx, para o token não aparecer em logs (do Airflow, por exemplo).
"""

import logging

import httpx

from crypto_analyzer.config import Settings

logger = logging.getLogger(__name__)

API_URL = "https://api.telegram.org"
# O Telegram recusa mensagens com mais de 4096 caracteres.
MAX_LENGTH = 4096


class TelegramError(Exception):
    """O Telegram não aceitou a mensagem (ou não respondeu)."""


def send_message(
    text: str, *, token: str, chat_id: str, client: httpx.Client | None = None
) -> None:
    """Envia `text` para `chat_id`. Levanta `TelegramError` sem expor o token."""
    owned = client is None
    http = client or httpx.Client(timeout=10)
    try:
        response = http.post(
            f"{API_URL}/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text[:MAX_LENGTH]},
        )
    except httpx.HTTPError as error:
        raise TelegramError(
            f"falha de rede ao falar com o Telegram ({type(error).__name__})"
        ) from None
    finally:
        if owned:
            http.close()
    if response.status_code != 200:
        raise TelegramError(
            f"o Telegram respondeu HTTP {response.status_code}: {_description(response)}"
        )


def notify(text: str, settings: Settings | None = None, client: httpx.Client | None = None) -> bool:
    """Envia o alerta se o Telegram estiver configurado; senão, só registra no log.

    Devolve se a mensagem foi enviada.
    """
    settings = settings or Settings()  # type: ignore[call-arg]
    if not (settings.telegram_bot_token and settings.telegram_chat_id):
        logger.warning("telegram: não configurado; alerta só no log: %s", text)
        return False
    send_message(
        text,
        token=settings.telegram_bot_token,
        chat_id=settings.telegram_chat_id,
        client=client,
    )
    logger.info("telegram: alerta enviado")
    return True


def _description(response: httpx.Response) -> str:
    try:
        return str(response.json().get("description", "sem descrição"))
    except ValueError:
        return "resposta não é JSON"
