import email

import pytest

from _common import (
    _decode_str,
    _get_body,
    _truncate_snippet,
    get_last_uid_current,
    get_new_messages,
    close_service,
)

# ---------- _truncate_snippet ----------


class TestTruncateSnippet:
    def test_short_text_not_truncated(self):
        assert _truncate_snippet("hello", limit=500) == "hello"

    def test_strips_whitespace(self):
        assert _truncate_snippet("  hello  ", limit=500) == "hello"

    def test_long_text_truncated_with_ellipsis(self):
        text = "word " * 200  # заведомо длиннее лимита
        result = _truncate_snippet(text, limit=20)
        assert result.endswith("…")
        assert len(result) <= 22  # 20 + "…" + возможный остаток слова

    def test_truncation_does_not_cut_word_in_half(self):
        text = "abcdefghij klmnopqrst"
        result = _truncate_snippet(text, limit=15)
        # обрезка идёт по rsplit(" ", 1) — не должно быть разорванного слова
        assert not result.rstrip("…").endswith(("abcdefghij kl",))
        assert result == "abcdefghij…"

    def test_exact_limit_length(self):
        text = "a" * 10
        assert _truncate_snippet(text, limit=10) == text


# ---------- _decode_str ----------


class TestDecodeStr:
    def test_none_returns_empty_string(self):
        assert _decode_str(None) == ""

    def test_empty_string_returns_empty_string(self):
        assert _decode_str("") == ""

    def test_plain_ascii_subject(self):
        assert _decode_str("Hello World") == "Hello World"

    def test_decodes_utf8_encoded_header(self):
        # имитация реального закодированного заголовка (как шлют многие MTA)
        from email.header import Header

        encoded = Header("Тема письма", "utf-8").encode()
        assert _decode_str(encoded) == "Тема письма"

    def test_decodes_mixed_encoded_and_plain_parts(self):
        from email.header import Header

        # заголовок с несколькими частями разных кодировок — частый кейс
        encoded = Header("Привет, ", "utf-8").encode() + " plain part"
        result = _decode_str(encoded)
        assert "Привет" in result
        assert "plain part" in result


# ---------- _get_body ----------


class TestGetBody:
    def test_plain_text_body(self, email_factory):
        raw = email_factory["plain"]("Subject", "a@b.com", "c@d.com", "Hello, world!")
        msg = email.message_from_bytes(raw)
        assert _get_body(msg) == "Hello, world!"

    def test_html_body_extracted_to_text(self, email_factory):
        html = "<html><body><p>Hello from HTML</p></body></html>"
        raw = email_factory["html"]("Subject", "a@b.com", "c@d.com", html)
        msg = email.message_from_bytes(raw)
        result = _get_body(msg)
        assert "Hello from HTML" in result
        # не должно остаться HTML-тегов
        assert "<p>" not in result
        assert "<html>" not in result

    def test_html_table_not_rendered_as_markdown_table(self, email_factory):
        # регрессионный тест на баг с html2text: ---|--- мусор от таблиц
        html = """
        <html><body>
        <table><tr><td>Cell A</td><td>Cell B</td></tr></table>
        <p>Real content here</p>
        </body></html>
        """
        raw = email_factory["html"]("Subject", "a@b.com", "c@d.com", html)
        msg = email.message_from_bytes(raw)
        result = _get_body(msg)
        assert "---|---" not in result
        assert "Real content here" in result

    def test_multipart_with_both_parts_uses_html_version(self, email_factory):
        # Регрессионный тест текущего поведения: _get_body проверяет
        # `if html_body:` раньше `elif plain_body:`, поэтому при наличии
        # ОБОИХ вариантов в multipart-письме побеждает HTML-версия,
        # даже если text/plain был найден первым при обходе частей.
        raw = email_factory["multipart"](
            "Subject",
            "a@b.com",
            "c@d.com",
            plain_body="Plain version text",
            html_body="<p>HTML version text</p>",
        )
        msg = email.message_from_bytes(raw)
        result = _get_body(msg)
        assert "HTML version text" in result
        assert "Plain version text" not in result

    def test_multipart_with_only_plain_part_uses_plain(self, email_factory):
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        msg = MIMEMultipart("mixed")
        msg["Subject"] = "Only plain"
        msg["From"] = "a@b.com"
        msg["To"] = "c@d.com"
        msg.attach(MIMEText("Only plain text here", "plain", "utf-8"))

        parsed = email.message_from_bytes(msg.as_bytes())
        result = _get_body(parsed)
        assert "Only plain text here" in result

    def test_html_fragment_without_html_body_wrapper_returns_empty(self, email_factory):
        # ВАЖНОЕ ОГРАНИЧЕНИЕ trafilatura: extract() возвращает None (и,
        # соответственно, _get_body — пустую строку) для HTML-фрагментов
        # без обёртки <html><body>...</body></html>. Реальные письма почти
        # всегда присылают полную структуру, но если какой-то отправитель
        # пришлёт "голый" HTML-фрагмент как text/html часть — уведомление
        # в Telegram придёт с пустым телом письма, без ошибки и без лога.
        import email as email_module
        from email.mime.text import MIMEText

        raw_fragment_only = MIMEText("<p>Just a fragment</p>", "html", "utf-8")
        raw_fragment_only["Subject"] = "Fragment"
        raw_fragment_only["From"] = "a@b.com"
        raw_fragment_only["To"] = "c@d.com"

        msg = email_module.message_from_bytes(raw_fragment_only.as_bytes())
        result = _get_body(msg)
        assert result == ""

    def test_empty_body_returns_empty_string(self):
        from email.message import EmailMessage

        msg = EmailMessage()
        msg["Subject"] = "No body"
        msg["From"] = "a@b.com"
        msg.set_content("")
        result = _get_body(msg)
        assert result == ""

    def test_body_respects_limit(self, email_factory):
        long_text = "word " * 1000
        raw = email_factory["plain"]("Subject", "a@b.com", "c@d.com", long_text)
        msg = email.message_from_bytes(raw)
        result = _get_body(msg, limit=50)
        assert len(result) <= 52
        assert result.endswith("…")

    def test_attachment_is_skipped_for_body_extraction(self, email_factory):
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        from email.mime.application import MIMEApplication

        msg = MIMEMultipart()
        msg["Subject"] = "With attachment"
        msg["From"] = "a@b.com"
        msg["To"] = "c@d.com"
        msg.attach(MIMEText("Actual body text", "plain", "utf-8"))

        attachment = MIMEApplication(b"fake pdf bytes", _subtype="pdf")
        attachment.add_header("Content-Disposition", "attachment", filename="file.pdf")
        msg.attach(attachment)

        parsed = email.message_from_bytes(msg.as_bytes())
        result = _get_body(parsed)
        assert "Actual body text" in result


# ---------- get_last_uid_current ----------


class TestGetLastUidCurrent:
    def test_returns_zero_when_mailbox_empty(self, fake_imap_factory):
        imap = fake_imap_factory(messages={})
        assert get_last_uid_current(imap) == 0

    def test_returns_highest_uid(self, fake_imap_factory):
        imap = fake_imap_factory(messages={5: b"", 12: b"", 3: b""})
        assert get_last_uid_current(imap) == 12

    def test_single_message(self, fake_imap_factory):
        imap = fake_imap_factory(messages={42: b""})
        assert get_last_uid_current(imap) == 42


# ---------- get_new_messages ----------


class TestGetNewMessages:
    def test_no_new_messages_returns_empty_list(self, fake_imap_factory):
        imap = fake_imap_factory(messages={})
        messages, max_uid = get_new_messages(imap, last_uid=10)
        assert messages == []
        assert max_uid == 10

    def test_fetches_only_messages_above_last_uid(
        self, fake_imap_factory, email_factory
    ):
        raw1 = email_factory["plain"]("Old", "a@b.com", "c@d.com", "old message")
        raw2 = email_factory["plain"]("New", "a@b.com", "c@d.com", "new message")
        imap = fake_imap_factory(messages={5: raw1, 10: raw2})

        messages, max_uid = get_new_messages(imap, last_uid=5)

        assert len(messages) == 1
        assert messages[0]["uid"] == 10
        assert messages[0]["subject"] == "New"
        assert max_uid == 10

    def test_returns_all_message_fields(self, fake_imap_factory, email_factory):
        raw = email_factory["plain"](
            "Test Subject", "sender@example.com", "recipient@example.com", "Body text"
        )
        imap = fake_imap_factory(messages={1: raw})

        messages, max_uid = get_new_messages(imap, last_uid=0)

        assert len(messages) == 1
        msg = messages[0]
        assert msg["uid"] == 1
        assert msg["subject"] == "Test Subject"
        assert msg["from"] == "sender@example.com"
        assert msg["to"] == "recipient@example.com"
        assert msg["body"] == "Body text"
        assert msg["date"] is not None

    def test_multiple_new_messages_returns_max_uid(
        self, fake_imap_factory, email_factory
    ):
        raw1 = email_factory["plain"]("S1", "a@b.com", "c@d.com", "msg1")
        raw2 = email_factory["plain"]("S2", "a@b.com", "c@d.com", "msg2")
        raw3 = email_factory["plain"]("S3", "a@b.com", "c@d.com", "msg3")
        imap = fake_imap_factory(messages={1: raw1, 2: raw2, 3: raw3})

        messages, max_uid = get_new_messages(imap, last_uid=0)

        assert len(messages) == 3
        assert max_uid == 3
        assert {m["uid"] for m in messages} == {1, 2, 3}

    def test_missing_subject_defaults_to_empty_string(self, fake_imap_factory):
        from email.message import EmailMessage

        msg = EmailMessage()
        msg["From"] = "a@b.com"
        msg["To"] = "c@d.com"
        msg.set_content("no subject here")
        imap = fake_imap_factory(messages={1: msg.as_bytes()})

        messages, _ = get_new_messages(imap, last_uid=0)

        assert messages[0]["subject"] == ""


# ---------- close_service ----------


class TestCloseService:
    def test_calls_close_and_logout(self, fake_imap_factory):
        imap = fake_imap_factory()
        close_service(imap)
        assert imap.closed is True
        assert imap.logged_out is True

    def test_logout_called_even_if_close_raises(self, fake_imap_factory):
        imap = fake_imap_factory()

        def raising_close():
            raise RuntimeError("boom")

        imap.close = raising_close
        close_service(imap)  # не должно падать
        assert imap.logged_out is True
