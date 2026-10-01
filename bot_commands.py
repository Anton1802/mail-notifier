import logging
from config import TELEGRAM_CHAT_ID
from db import add_account, list_accounts, remove_account, toggle_account

from telegram import BotCommand, Update
from telegram.ext import Application, CommandHandler, ContextTypes

ALLOWED_CHAT_IDS = {int(TELEGRAM_CHAT_ID)}

logger = logging.getLogger(__name__)

# (команда, короткое описание для меню Telegram, формат для справки)
COMMANDS = [
    (
        "add_account",
        "Добавить аккаунт",
        "/add_account key|Имя|host|port|login|password",
    ),
    ("list_accounts", "Список аккаунтов", "/list_accounts"),
    ("remove_account", "Удалить аккаунт", "/remove_account key"),
    ("toggle_account", "Включить/выключить аккаунт", "/toggle_account key on|off"),
    ("help", "Показать справку", "/help"),
]

HELP_TEXT = "Доступные команды:\n\n" + "\n\n".join(
    f"{usage}\n    {desc}" for _, desc, usage in COMMANDS
)


def authorized(update: Update) -> bool:
    return update.effective_chat.id in ALLOWED_CHAT_IDS


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    await update.message.reply_text(HELP_TEXT)


async def add_account_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    # Формат: /add_account key|Название|host|port|login|password
    try:
        args_str = " ".join(context.args)
        key, name, host, port, login, password = args_str.split("|")
        conn = context.bot_data["db_conn"]
        add_account(
            conn,
            key.strip(),
            name.strip(),
            host.strip(),
            int(port.strip()),
            login.strip(),
            password.strip(),
            update.effective_chat.id,
        )
        await update.message.reply_text(f"✅ Аккаунт «{name.strip()}» добавлен")
        # рекомендую сразу удалить сообщение с паролем
        await context.bot.delete_message(
            update.effective_chat.id, update.message.message_id
        )
    except Exception as e:
        await update.message.reply_text(
            f"❌ Ошибка: {e}\n\nФормат:\n/add_account key|Имя|host|port|login|password"
        )


async def list_accounts_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    conn = context.bot_data["db_conn"]
    accounts = list_accounts(conn, enabled_only=False)
    if not accounts:
        await update.message.reply_text("Аккаунтов пока нет")
        return
    lines = [
        f"{'✅' if a['enabled'] else '⏸'} {a['provider_key']} — {a['display_name']} ({a['login']})"
        for a in accounts
    ]
    await update.message.reply_text("\n".join(lines))


async def remove_account_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    if not context.args:
        await update.message.reply_text("Формат: /remove_account key")
        return
    conn = context.bot_data["db_conn"]
    remove_account(conn, context.args[0])
    await update.message.reply_text(f"🗑 Аккаунт «{context.args[0]}» удалён")


async def toggle_account_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    if len(context.args) < 2:
        await update.message.reply_text("Формат: /toggle_account key on|off")
        return
    conn = context.bot_data["db_conn"]
    toggle_account(conn, context.args[0], context.args[1].lower() == "on")
    await update.message.reply_text(f"Готово: {context.args[0]} → {context.args[1]}")


async def post_init(app: Application):
    # Команды появятся в меню "/" в чате с ботом
    await app.bot.set_my_commands(
        [BotCommand(name, desc) for name, desc, _ in COMMANDS]
    )


def run_bot(conn, token):
    app = Application.builder().token(token).post_init(post_init).build()
    app.bot_data["db_conn"] = conn

    app.add_handler(CommandHandler("add_account", add_account_cmd))
    app.add_handler(CommandHandler("list_accounts", list_accounts_cmd))
    app.add_handler(CommandHandler("remove_account", remove_account_cmd))
    app.add_handler(CommandHandler("toggle_account", toggle_account_cmd))
    app.add_handler(CommandHandler("help", help_cmd))

    app.run_polling(stop_signals=None)
