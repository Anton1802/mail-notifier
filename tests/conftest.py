import email
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import pytest


@pytest.fixture
def db_conn(tmp_path, monkeypatch):
    """
    Свежая SQLite БД во временной директории для каждого теста.
    Переопределяем DB_PATH ДО импорта/вызова init_db, чтобы не задеть
    продовую state.db и не шарить состояние между тестами.
    """
    db_file = tmp_path / "test_state.db"
    monkeypatch.setenv("DB_PATH", str(db_file))

    from db import init_db

    conn = init_db()
    yield conn
    conn.close()


class FakeIMAP:
    """
    Мок IMAP-клиента, имитирующий минимально нужный интерфейс imaplib.IMAP4_SSL:
    .uid("search", ...), .uid("fetch", ...), .close(), .logout().

    messages: dict {uid_int: raw_bytes_письма}
    """

    def __init__(self, messages=None):
        self.messages = messages or {}
        self.closed = False
        self.logged_out = False
        self.fetch_calls = []

    def uid(self, command, *args):
        if command == "search":
            criteria = args[-1]
            all_uids = sorted(self.messages.keys())

            if criteria == "ALL":
                if not all_uids:
                    return "OK", [b""]
                return "OK", [" ".join(str(u) for u in all_uids).encode()]

            if criteria.startswith("UID "):
                start_part = criteria.split(" ", 1)[1]
                start_uid = int(start_part.split(":")[0])
                matched = [u for u in all_uids if u >= start_uid]
                if not matched:
                    return "OK", [b""]
                return "OK", [" ".join(str(u) for u in matched).encode()]

            return "OK", [b""]

        if command == "fetch":
            uid_bytes = args[0]
            uid = int(uid_bytes)
            self.fetch_calls.append(uid)
            if uid not in self.messages:
                return "NO", None
            raw = self.messages[uid]
            return "OK", [(f"{uid} (RFC822)".encode(), raw)]

        raise ValueError(f"Unexpected IMAP command: {command}")

    def close(self):
        self.closed = True

    def logout(self):
        self.logged_out = True


@pytest.fixture
def fake_imap_factory():
    """Фабрика для создания FakeIMAP с заданными письмами."""
    return FakeIMAP


def make_plain_email(subject, sender, to, body, date="Mon, 1 Jan 2026 10:00:00 +0000"):
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to
    msg["Date"] = date
    return msg.as_bytes()


def _wrap_html_fragment(html_fragment):
    if "<html" in html_fragment.lower():
        return html_fragment
    return f"<html><body>{html_fragment}</body></html>"


def make_html_email(subject, sender, to, html_body, date="Mon, 1 Jan 2026 10:00:00 +0000"):
    msg = MIMEText(_wrap_html_fragment(html_body), "html", "utf-8")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to
    msg["Date"] = date
    return msg.as_bytes()


def make_multipart_email(subject, sender, to, plain_body, html_body,
                          date="Mon, 1 Jan 2026 10:00:00 +0000"):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to
    msg["Date"] = date
    msg.attach(MIMEText(plain_body, "plain", "utf-8"))
    msg.attach(MIMEText(_wrap_html_fragment(html_body), "html", "utf-8"))
    return msg.as_bytes()


@pytest.fixture
def email_factory():
    """Фабрика для быстрого создания raw-писем разных типов."""
    return {
        "plain": make_plain_email,
        "html": make_html_email,
        "multipart": make_multipart_email,
    }
