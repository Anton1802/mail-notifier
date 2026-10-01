from unittest.mock import patch, MagicMock

import pytest

from db import add_account, get_last_uid
from main import format_message, poll_provider, poll_all_accounts

# ---------- format_message ----------


class TestFormatMessage:
    def test_contains_all_fields(self):
        text = format_message(
            sender="a@b.com",
            subject="Hello",
            snippet="Body text",
            service_name="Gmail",
        )
        assert "Gmail" in text
        assert "a@b.com" in text
        assert "Hello" in text
        assert "Body text" in text

    def test_starts_with_emoji_and_service_name(self):
        text = format_message("a@b.com", "Subj", "Snip", "Mail.ru")
        assert text.startswith("📧 Mail.ru")

    def test_empty_snippet_does_not_crash(self):
        text = format_message("a@b.com", "Subj", "", "Gmail")
        assert "Subj" in text


def _account_row(db_conn, **overrides):
    """Хелпер: добавляет аккаунт в БД и возвращает его строку из list_accounts."""
    from db import list_accounts

    defaults = dict(
        provider_key="test_acc",
        display_name="Test Account",
        host="imap.test.com",
        port=993,
        login="user@test.com",
        password="pass",
        owner_chat_id=1,
    )
    defaults.update(overrides)
    add_account(db_conn, **defaults)
    accounts = list_accounts(db_conn, enabled_only=False)
    return [a for a in accounts if a["provider_key"] == defaults["provider_key"]][0]


# ---------- poll_provider ----------


class TestPollProvider:
    @patch("main.close_service")
    @patch("main.telegram_bot_sendtext")
    @patch("main.get_service")
    def test_first_run_initializes_uid_without_sending_messages(
        self,
        mock_get_service,
        mock_send,
        mock_close,
        db_conn,
        fake_imap_factory,
        email_factory,
    ):
        raw = email_factory["plain"]("Subj", "a@b.com", "c@d.com", "body")
        fake_imap = fake_imap_factory(messages={1: raw, 2: raw})
        mock_get_service.return_value = fake_imap

        account = _account_row(db_conn)
        poll_provider(db_conn, account)

        # первый запуск — просто запоминаем текущий uid, ничего не шлём
        mock_send.assert_not_called()
        assert get_last_uid(db_conn, "test_acc") == 2

    @patch("main.close_service")
    @patch("main.telegram_bot_sendtext")
    @patch("main.get_service")
    def test_sends_new_messages_to_telegram(
        self,
        mock_get_service,
        mock_send,
        mock_close,
        db_conn,
        fake_imap_factory,
        email_factory,
    ):
        from db import save_last_uid

        raw_old = email_factory["plain"]("Old", "a@b.com", "c@d.com", "old")
        raw_new = email_factory["plain"]("New", "x@y.com", "c@d.com", "new body")
        fake_imap = fake_imap_factory(messages={1: raw_old, 2: raw_new})
        mock_get_service.return_value = fake_imap

        account = _account_row(db_conn)
        save_last_uid(db_conn, 1, "test_acc")  # уже видели uid=1

        poll_provider(db_conn, account)

        mock_send.assert_called_once()
        sent_text = mock_send.call_args[0][0]
        assert "New" in sent_text
        assert "new body" in sent_text
        assert get_last_uid(db_conn, "test_acc") == 2

    @patch("main.close_service")
    @patch("main.telegram_bot_sendtext")
    @patch("main.get_service")
    def test_no_new_messages_sends_nothing(
        self, mock_get_service, mock_send, mock_close, db_conn, fake_imap_factory
    ):
        from db import save_last_uid

        fake_imap = fake_imap_factory(messages={})
        mock_get_service.return_value = fake_imap

        account = _account_row(db_conn)
        save_last_uid(db_conn, 5, "test_acc")

        poll_provider(db_conn, account)

        mock_send.assert_not_called()

    @patch("main.get_service")
    def test_connection_failure_is_caught_and_logged(self, mock_get_service, db_conn):
        mock_get_service.side_effect = RuntimeError("connection refused")
        account = _account_row(db_conn)

        # не должно пробрасывать исключение наружу
        poll_provider(db_conn, account)

    @patch("main.close_service")
    @patch("main.telegram_bot_sendtext")
    @patch("main.get_service")
    def test_telegram_send_failure_does_not_block_other_messages(
        self,
        mock_get_service,
        mock_send,
        mock_close,
        db_conn,
        fake_imap_factory,
        email_factory,
    ):
        from db import save_last_uid

        raw1 = email_factory["plain"]("S1", "a@b.com", "c@d.com", "msg1")
        raw2 = email_factory["plain"]("S2", "a@b.com", "c@d.com", "msg2")
        fake_imap = fake_imap_factory(messages={1: raw1, 2: raw2})
        mock_get_service.return_value = fake_imap

        mock_send.side_effect = [RuntimeError("telegram down"), None]

        account = _account_row(db_conn)
        save_last_uid(db_conn, 0, "test_acc")

        poll_provider(db_conn, account)  # не должно падать

        assert mock_send.call_count == 2
        # last_uid всё равно обновляется, даже если отправка упала
        assert get_last_uid(db_conn, "test_acc") == 2

    @patch("main.close_service")
    @patch("main.get_service")
    def test_imap_closed_even_when_fetch_and_recovery_both_fail(
        self, mock_get_service, mock_close, db_conn, fake_imap_factory
    ):
        # Регрессионный тест текущего поведения: если и get_new_messages,
        # и последующий fallback-вызов get_last_uid_current (внутри
        # except-ветки) оба падают, poll_provider пробрасывает исключение
        # наружу — но IMAP-соединение всё равно должно быть закрыто
        # благодаря finally. Это же защищает caller (poll_all_accounts /
        # main) от утечки соединений, даже если сам IMAP "сломан".
        from db import save_last_uid

        fake_imap = fake_imap_factory(messages={})

        def broken_uid(command, *args):
            raise RuntimeError("IMAP connection broke")

        fake_imap.uid = broken_uid
        mock_get_service.return_value = fake_imap

        account = _account_row(db_conn)
        save_last_uid(db_conn, 0, "test_acc")  # last_uid уже не None

        with pytest.raises(RuntimeError, match="IMAP connection broke"):
            poll_provider(db_conn, account)

        mock_close.assert_called_once_with(fake_imap)

    @patch("main.close_service")
    @patch("main.telegram_bot_sendtext")
    @patch("main.get_service")
    def test_imap_closed_normally_after_successful_poll(
        self,
        mock_get_service,
        mock_send,
        mock_close,
        db_conn,
        fake_imap_factory,
        email_factory,
    ):
        from db import save_last_uid

        raw = email_factory["plain"]("S1", "a@b.com", "c@d.com", "msg1")
        fake_imap = fake_imap_factory(messages={1: raw})
        mock_get_service.return_value = fake_imap

        account = _account_row(db_conn)
        save_last_uid(db_conn, 0, "test_acc")

        poll_provider(db_conn, account)

        mock_close.assert_called_once_with(fake_imap)


# ---------- poll_all_accounts ----------


class TestPollAllAccounts:
    @patch("main.poll_provider")
    def test_polls_each_enabled_account(self, mock_poll, db_conn):
        add_account(db_conn, "acc1", "Account 1", "h1", 993, "l1", "p1", 1)
        add_account(db_conn, "acc2", "Account 2", "h2", 993, "l2", "p2", 1)

        poll_all_accounts(db_conn)

        assert mock_poll.call_count == 2
        polled_keys = {
            call.args[1]["provider_key"] for call in mock_poll.call_args_list
        }
        assert polled_keys == {"acc1", "acc2"}

    @patch("main.poll_provider")
    def test_skips_disabled_accounts(self, mock_poll, db_conn):
        from db import toggle_account

        add_account(db_conn, "enabled_acc", "Enabled", "h1", 993, "l1", "p1", 1)
        add_account(db_conn, "disabled_acc", "Disabled", "h2", 993, "l2", "p2", 1)
        toggle_account(db_conn, "disabled_acc", enabled=False)

        poll_all_accounts(db_conn)

        assert mock_poll.call_count == 1
        assert mock_poll.call_args[0][1]["provider_key"] == "enabled_acc"

    @patch("main.poll_provider")
    def test_no_accounts_does_not_call_poll_provider(self, mock_poll, db_conn):
        poll_all_accounts(db_conn)
        mock_poll.assert_not_called()
