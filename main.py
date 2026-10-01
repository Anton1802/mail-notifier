import logging
import threading
import time
from config import *

from _common import get_service, get_new_messages, close_service, get_last_uid_current
from db import init_db, get_last_uid, save_last_uid, list_accounts

from telegram_notify import telegram_bot_sendtext
from bot_commands import run_bot

logger = logging.getLogger(__name__)
_format = "%(asctime)s %(levelname)s %(message)s"

POLL_INTERVAL_SECONDS = 60


def format_message(sender, subject, snippet, service_name):
    return (
        f"📧 {service_name} Новое письмо\n\nОт: {sender}\nТема: {subject}\n\n{snippet}"
    )


def poll_all_accounts(conn):
    for account in list_accounts(conn, enabled_only=True):
        poll_provider(conn, account)


def poll_provider(conn, account):
    last_uid = get_last_uid(conn, account["provider_key"])
    try:
        imap = get_service(
            host=account["host"],
            port=account["port"],
            login=account["login"],
            password=account["password"],
        )
    except Exception as e:
        logger.error("Failed to connect to %s IMAP: %s", account["display_name"], e)
        return

    try:
        if last_uid is None:
            current_uid = get_last_uid_current(imap)
            save_last_uid(conn, current_uid, account["provider_key"])
            logger.info(
                "Initialized %s last_uid=%s", account["display_name"], current_uid
            )
            return
        try:
            messages, new_last_uid = get_new_messages(imap, last_uid, mark_read=True)
        except Exception as e:
            logger.warning(
                "Failed to fetch %s messages (%s), resetting last_uid",
                account["display_name"],
                e,
            )
            save_last_uid(conn, get_last_uid_current(imap), account["provider_key"])
            return

        for message in messages:
            try:
                text = format_message(
                    message["from"],
                    message["subject"] or "(без темы)",
                    message["body"],
                    account["display_name"],
                )
                telegram_bot_sendtext(text)
            except Exception as e:
                logger.error(
                    "Failed to send %s message: %s", account["display_name"], e
                )

        save_last_uid(conn, new_last_uid, account["provider_key"])
    finally:
        close_service(imap)


def main():
    logging.basicConfig(level=logging.INFO, format=_format)
    conn = init_db()

    print("Mail start pulling...")

    # отдельное соединение для бота — не шарим conn между потоками
    bot_conn = init_db()
    bot_thread = threading.Thread(
        target=run_bot,
        args=(bot_conn, TELEGRAM_BOT_TOKEN),
        daemon=True,
    )
    bot_thread.start()

    while True:
        try:
            poll_all_accounts(conn)
        except Exception as e:
            logger.exception("Unexpected error during poll cycle: %s", e)
        time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
