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
from mailru import (
    get_service as get_mailru_service,
    get_last_uid_current,
    get_new_messages as get_new_mailru_messages,
    close_service as close_mailru_service,
)
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


def poll_mailru(conn):
    last_uid = get_last_uid_mailru(conn)

    try:
        imap = get_mailru_service()
    except Exception as e:
        logger.error("Failed to connect to Mail.ru IMAP: %s", e)
        return

    try:
        if last_uid is None:
            # Первый запуск — просто запоминаем текущий UID, письма не шлём
            current_uid = get_last_uid_current(imap)
            save_last_uid_mailru(conn, current_uid)
            logger.info(
                "Initialized Mail.ru last_uid=%s (no messages sent)", current_uid
            )
            return

        try:
            messages, new_last_uid = get_new_mailru_messages(
                imap, last_uid, mark_read=True
            )
        except Exception as e:
            logger.warning(
                "Failed to fetch Mail.ru messages (%s), resetting last_uid", e
            )
            current_uid = get_last_uid_current(imap)
            save_last_uid_mailru(conn, current_uid)
            return

        for message in messages:
            try:
                text = format_message(
                    message["from"],
                    message["subject"] or "(без темы)",
                    message["body"][:500],
                    "Mail.ru",
                )
                telegram_bot_sendtext(text)
                logger.info(text)
            except Exception as e:
                logger.error("Failed to send Mail.ru message to Telegram: %s", e)

        save_last_uid_mailru(conn, new_last_uid)
        if messages:
            logger.info("Sent %d new Mail.ru message(s) to Telegram", len(messages))
    finally:
        close_mailru_service(imap)


def main():
    logging.basicConfig(level=logging.INFO, format=_format)
    logger.info("Mail notifier started")

    conn = init_db()
    gmail_service = get_service()

    print("Mail start pulling...")

    while True:
        try:
            poll_gmail(gmail_service, conn)
        except Exception as e:
            logger.exception("Unexpected error during Gmail poll: %s", e)

        try:
            poll_mailru(conn)
        except Exception as e:
            logger.exception("Unexpected error during Mail.ru poll: %s", e)

        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
