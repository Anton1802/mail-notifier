import requests
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
import logging

logger = logging.getLogger(__name__)

if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    msg = "ERROR: Telegram chat id or bot token not transferred!"
    logger.error(msg)
    raise ValueError(msg)


def telegram_bot_sendtext(bot_message):

    bot_token = TELEGRAM_BOT_TOKEN
    bot_chatID = TELEGRAM_CHAT_ID
    send_text = (
        "https://api.telegram.org/bot"
        + bot_token
        + "/sendMessage?chat_id="
        + bot_chatID
        + "&parse_mode=Markdown&text="
        + bot_message
    )

    response = requests.get(send_text)

    return response.json()
