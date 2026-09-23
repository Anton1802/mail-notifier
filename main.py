import logging
import time

from db import (
    init_db,
    get_last_history_id,
    save_last_history_id,
    get_last_uid_mailru,
    save_last_uid_mailru,
)
from gmail import get_service, get_last_history_google, get_new_messages
from telegram import telegram_bot_sendtext

logger = logging.getLogger(__name__)
_format = "%(asctime)s %(levelname)s %(message)s"

POLL_INTERVAL_SECONDS = 60


def get_header(message, name):
    headers = message.get("payload", {}).get("headers", [])
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def get_body_snippet(message):
    # snippet — короткий превью-текст, который Gmail сам генерирует
    return message.get("snippet", "")


def format_message(sender, subject, snippet, service_name):
    return f"📧 *{service_name} Новое письмо*\n\n*От:* {sender}\n*Тема:* {subject}\n\n{snippet}"


def poll_gmail(service, conn):
    last_history_id = get_last_history_id(conn)

    if last_history_id is None:
        # Первый запуск — просто запоминаем текущий historyId, письма не шлём
        current_id = get_last_history_google(service)
        save_last_history_id(conn, current_id)
        logger.info("Initialized Gmail history_id=%s (no messages sent)", current_id)
        return

    try:
        messages, new_history_id = get_new_messages(service, last_history_id)
    except Exception as e:
        # historyId мог протухнуть (Gmail хранит историю ограниченное время)
        logger.warning("Failed to fetch Gmail history (%s), resetting history_id", e)
        current_id = get_last_history_google(service)
        save_last_history_id(conn, current_id)
        return

    for message in messages:
        try:
            sender = get_header(message, "From")
            subject = get_header(message, "Subject") or "(без темы)"
            snippet = get_body_snippet(message)
            text = format_message(sender, subject, snippet, "Gmail")
            telegram_bot_sendtext(text)
            logger.info(text)
        except Exception as e:
            logger.error("Failed to send Gmail message to Telegram: %s", e)

    save_last_history_id(conn, new_history_id)
    if messages:
        logger.info("Sent %d new Gmail message(s) to Telegram", len(messages))


def main():
    logging.basicConfig(level=logging.INFO, filename="main.log", format=_format)
    logger.info("Mail notifier started")

    conn = init_db()
    gmail_service = get_service()

    print("Mail start pulling...")

    while True:
        try:
            poll_gmail(gmail_service, conn)
        except Exception as e:
            logger.exception("Unexpected error during Gmail poll: %s", e)

        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
