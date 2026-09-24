# 📬 Mail Notifier

Лёгкий self-hosted бот, который следит за новыми письмами в почтовых ящиках (Gmail, Mail.ru) по IMAP и присылает уведомления в Telegram.

## ✨ Возможности

- 🔄 Периодический опрос нескольких почтовых провайдеров (Gmail, Mail.ru — легко добавить ещё)
- 📨 Уведомления в Telegram с темой письма, отправителем и превью текста
- 💾 Хранение состояния (последний прочитанный UID) в локальной SQLite-базе — без внешних зависимостей
- 🛡️ Устойчивость к ошибкам: сбой одного провайдера не останавливает опрос остальных
- 🏠 Полностью self-hosted — все данные остаются под вашим контролем

## 📦 Структура проекта

```
mail-notifier/
├── main.py       # точка входа, цикл опроса
├── _common.py    # работа с IMAP (подключение, чтение писем)
├── db.py         # хранение последнего UID в SQLite
├── telegram.py   # отправка сообщений в Telegram
├── config.py     # переменные конфигурации (не в репозитории)
└── state.db      # создаётся автоматически при первом запуске
```

## ⚙️ Установка

```bash
git clone <repo-url>
cd mail-notifier
pip install -r requirements.txt
```

Понадобится:
- `requests`

## 🔑 Конфигурация

Создайте файл `config.py` в корне проекта:

```python
# Mail.ru
MAILRU_EMAIL = "you@mail.ru"
MAILRU_APP_PASSWORD = "xxxx-xxxx-xxxx-xxxx"

# Gmail
GMAIL_EMAIL = "you@gmail.com"
GMAIL_APP_PASSWORD = "xxxx-xxxx-xxxx-xxxx"

# Telegram
TELEGRAM_BOT_TOKEN = "123456:ABC-DEF..."
TELEGRAM_CHAT_ID = "123456789"
```

> ⚠️ Используйте **пароли приложений** (app passwords), а не основной пароль от почты — обычный пароль IMAP не примет при включённой двухфакторной аутентификации.

### Как получить пароль приложения

- **Gmail**: [Управление аккаунтом Google → Безопасность → Пароли приложений](https://myaccount.google.com/apppasswords) (нужна включённая 2FA)
- **Mail.ru**: Настройки → Пароль и безопасность → Пароли для внешних приложений

### Как получить Telegram Bot Token и Chat ID

1. Создайте бота через [@BotFather](https://t.me/BotFather) → получите `TELEGRAM_BOT_TOKEN`
2. Напишите боту любое сообщение
3. Откройте `https://api.telegram.org/bot<TOKEN>/getUpdates` и найдите `chat.id` в ответе

## 🚀 Запуск

```bash
python3 main.py
```

При первом запуске бот **не отправляет** уведомления о существующих письмах — он запоминает текущий последний UID для каждого ящика и с этого момента отслеживает только новые.

Логи выводятся в консоль в формате:

```
2026-09-24 22:49:42,414 INFO Mail notifier started
2026-09-24 22:49:42,415 INFO Initialized Mail.ru last_uid=1523 (no messages sent)
```

### Запуск в фоне (systemd)

Пример unit-файла `/etc/systemd/system/mail-notifier.service`:

```ini
[Unit]
Description=Mail Notifier Bot
After=network.target

[Service]
Type=simple
WorkingDirectory=/home/vboxuser/mail-notifier
ExecStart=/usr/bin/python3 /home/vboxuser/mail-notifier/main.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now mail-notifier
sudo journalctl -u mail-notifier -f
```

## 🧩 Добавление нового провайдера

1. Добавьте учётные данные в `config.py`
2. Добавьте запись в `IMAP_PROVIDERS` в `main.py`:

```python
IMAP_PROVIDERS = {
    "mailru": ("imap.mail.ru", 993, MAILRU_EMAIL, MAILRU_APP_PASSWORD),
    "gmail": ("imap.gmail.com", 993, GMAIL_EMAIL, GMAIL_APP_PASSWORD),
    "yandex": ("imap.yandex.ru", 993, YANDEX_EMAIL, YANDEX_APP_PASSWORD),
}
```

3. Добавьте функцию-обёртку и вызов в цикле `main()`:

```python
def poll_yandex(conn):
    poll_provider(conn, "yandex", "Yandex")
```

```python
try:
    poll_yandex(conn)
except Exception as e:
    logger.exception("Unexpected error during Yandex poll: %s", e)
```

## 🛠️ Настройки

| Параметр | Где | Описание |
|---|---|---|
| `POLL_INTERVAL_SECONDS` | `main.py` | Интервал опроса почты в секундах (по умолчанию 60) |
| `mark_read` | `get_new_messages()` | Помечать ли письма прочитанными после получения |

## 🐛 Известные особенности

- Состояние (`last_uid`) хранится в SQLite (`state.db`) — при удалении файла бот заново инициализируется и не пришлёт старые письма
- Если провайдер временно недоступен, ошибка логируется, но не прерывает работу остальных провайдеров

## 📄 Лицензия

MIT
