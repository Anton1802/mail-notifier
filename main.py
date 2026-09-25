import logging
import time

from _common import get_service, get_new_messages, close_service, get_last_uid_current

from config import *

from db import init_db, get_last_uid, save_last_uid
from telegram import telegram_bot_sendtext

logger = logging.getLogger(__name__)
_format = "%(asctime)s %(levelname)s %(message)s"

POLL_INTERVAL_SECONDS = 60

IMAP_PROVIDERS = {
    # "mailru": (MAILRU_HOST, MAILRU_PORT, MAILRU_EMAIL, MAILRU_APP_PASSWORD),
    # "yandex": (...),
    "mailru": ("imap.mail.ru", 993, MAILRU_EMAIL, MAILRU_APP_PASSWORD),
    "gmail": ("imap.gmail.com", 993, GMAIL_EMAIL, GMAIL_APP_PASSWORD),
}


def format_message(sender, subject, snippet, service_name):
    return (
        f"📧 {service_name} Новое письмо\n\nОт: {sender}\nТема: {subject}\n\n{snippet}"
    )


def poll_provider(conn, provider_key, service_name):
    host, port, login, password = IMAP_PROVIDERS[provider_key]
    last_uid = get_last_uid(conn, provider_key)

    try:
        imap = get_service(
            host=host,
            port=port,
            login=login,
            password=password,
        )
    except Exception as e:
        logger.error("Failed to connect to %s IMAP: %s", service_name, e)
        return

    try:
        if last_uid is None:
            # Первый запуск — просто запоминаем текущий UID, письма не шлём
            current_uid = get_last_uid_current(imap)
            save_last_uid(conn, current_uid, provider_key)
            logger.info(
                "Initialized %s last_uid=%s (no messages sent)",
                service_name,
                current_uid,
            )
            return

        try:
            messages, new_last_uid = get_new_messages(imap, last_uid, mark_read=True)
        except Exception as e:
            logger.warning(
                "Failed to fetch %s messages (%s), resetting last_uid", service_name, e
            )
            current_uid = get_last_uid_current(imap)
            save_last_uid(conn, current_uid, provider_key)
            return

        for message in messages:
            try:
                text = format_message(
                    message["from"],
                    message["subject"] or "(без темы)",
                    message["body"],
                    service_name,
                )
                telegram_bot_sendtext(text)
                logger.info(text)
            except Exception as e:
                logger.error(
                    "Failed to send %s message to Telegram: %s", service_name, e
                )

        save_last_uid(conn, new_last_uid, provider_key)
        if messages:
            logger.info(
                "Sent %d new %s message(s) to Telegram", len(messages), service_name
            )
    finally:
        close_service(imap)


def poll_mailru(conn):
    poll_provider(conn, "mailru", "Mail.ru")


def poll_gmail(conn):
    poll_provider(conn, "gmail", "Gmail")


def main():
    logging.basicConfig(level=logging.INFO, format=_format)
    logger.info("Mail notifier started")

    conn = init_db()

    print("Mail start pulling...")

    while True:
        try:
            poll_mailru(conn)
        except Exception as e:
            logger.exception("Unexpected error during Mail.ru poll: %s", e)

        try:
            poll_gmail(conn)
        except Exception as e:
            logger.exception("Unexpected error during Gmail poll: %s", e)

        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
