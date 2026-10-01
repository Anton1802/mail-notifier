import requests
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
import logging

logger = logging.getLogger(__name__)

if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    msg = "ERROR: Telegram chat id or bot token not transferred!"
    logger.error(msg)
    raise ValueError(msg)


def telegram_bot_sendtext(bot_message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    params = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": bot_message,
    }

    response = requests.get(url, params=params, timeout=10)
    data = response.json()

    if not data.get("ok"):
        logger.error("Telegram API error: %s", data)

    return data
