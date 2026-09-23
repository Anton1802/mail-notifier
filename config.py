import os
from dotenv import load_dotenv

load_dotenv()

GOOGLE_CREDENTIALS = os.getenv("GOOGLE_CREDENTIALS")

MAILRU_EMAIL = os.getenv("MAILRU_EMAIL")
MAILRU_APP_PASSWORD = os.getenv("MAILRU_APP_PASSWORD")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
