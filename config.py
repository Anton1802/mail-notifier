import os
from dotenv import load_dotenv

load_dotenv()

GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS")

MAILRU_USER = os.getenv("MAILRU_USER")
MAILRU_PASSWORD = os.getenv("MAILRU_PASSWORD")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
