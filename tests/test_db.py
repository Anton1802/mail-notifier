import sqlite3

import pytest

from db import (
    add_account,
    get_last_uid,
    get_state,
    list_accounts,
    remove_account,
    save_last_uid,
    save_state,
    toggle_account,
)

# ---------- state / last_uid ----------


class TestState:
    def test_get_state_returns_none_when_missing(self, db_conn):
        assert get_state(db_conn, "nonexistent_key") is None

    def test_save_and_get_state_roundtrip(self, db_conn):
        save_state(db_conn, "my_key", "my_value")
        assert get_state(db_conn, "my_key") == "my_value"

    def test_save_state_overwrites_existing_value(self, db_conn):
        save_state(db_conn, "key1", "first")
        save_state(db_conn, "key1", "second")
        assert get_state(db_conn, "key1") == "second"

    def test_save_state_stores_as_string(self, db_conn):
        save_state(db_conn, "numeric_key", 12345)
        # get_state не кастует обратно — возвращает строку как есть
        assert get_state(db_conn, "numeric_key") == "12345"


class TestLastUid:
    def test_get_last_uid_none_when_not_set(self, db_conn):
        assert get_last_uid(db_conn, "gmail") is None

    def test_save_and_get_last_uid_roundtrip(self, db_conn):
        save_last_uid(db_conn, 42, "gmail")
        assert get_last_uid(db_conn, "gmail") == 42

    def test_last_uid_is_returned_as_int(self, db_conn):
        save_last_uid(db_conn, 100, "mailru")
        result = get_last_uid(db_conn, "mailru")
        assert isinstance(result, int)

    def test_last_uid_namespaced_per_provider(self, db_conn):
        save_last_uid(db_conn, 10, "gmail")
        save_last_uid(db_conn, 20, "mailru")
        assert get_last_uid(db_conn, "gmail") == 10
        assert get_last_uid(db_conn, "mailru") == 20

    def test_update_last_uid_overwrites(self, db_conn):
        save_last_uid(db_conn, 5, "gmail")
        save_last_uid(db_conn, 99, "gmail")
        assert get_last_uid(db_conn, "gmail") == 99


# ---------- mail_accounts CRUD ----------


class TestAddAccount:
    def test_add_account_persists_all_fields(self, db_conn):
        add_account(
            db_conn,
            provider_key="work_gmail",
            display_name="Work Gmail",
            host="imap.gmail.com",
            port=993,
            login="user@gmail.com",
            password="secret",
            owner_chat_id=123456,
        )
        accounts = list_accounts(db_conn, enabled_only=False)
        assert len(accounts) == 1
        acc = accounts[0]
        assert acc["provider_key"] == "work_gmail"
        assert acc["display_name"] == "Work Gmail"
        assert acc["host"] == "imap.gmail.com"
        assert acc["port"] == 993
        assert acc["login"] == "user@gmail.com"
        assert acc["password"] == "secret"
        assert acc["owner_chat_id"] == 123456

    def test_new_account_is_enabled_by_default(self, db_conn):
        add_account(db_conn, "k1", "Name", "host", 993, "login", "pass", 1)
        accounts = list_accounts(db_conn, enabled_only=False)
        assert accounts[0]["enabled"] == 1

    def test_duplicate_provider_key_raises(self, db_conn):
        add_account(db_conn, "dup_key", "First", "host1", 993, "l1", "p1", 1)
        with pytest.raises(sqlite3.IntegrityError):
            add_account(db_conn, "dup_key", "Second", "host2", 993, "l2", "p2", 1)


class TestListAccounts:
    def test_empty_db_returns_empty_list(self, db_conn):
        assert list(list_accounts(db_conn)) == []

    def test_enabled_only_filters_disabled_accounts(self, db_conn):
        add_account(db_conn, "acc1", "Account 1", "h1", 993, "l1", "p1", 1)
        add_account(db_conn, "acc2", "Account 2", "h2", 993, "l2", "p2", 1)
        toggle_account(db_conn, "acc2", enabled=False)

        enabled = list_accounts(db_conn, enabled_only=True)
        all_accounts = list_accounts(db_conn, enabled_only=False)

        assert len(enabled) == 1
        assert enabled[0]["provider_key"] == "acc1"
        assert len(all_accounts) == 2

    def test_default_enabled_only_is_true(self, db_conn):
        add_account(db_conn, "acc1", "Account 1", "h1", 993, "l1", "p1", 1)
        toggle_account(db_conn, "acc1", enabled=False)
        # вызов без аргумента enabled_only должен по умолчанию фильтровать
        assert list(list_accounts(db_conn)) == []


class TestRemoveAccount:
    def test_remove_existing_account(self, db_conn):
        add_account(db_conn, "to_remove", "Name", "host", 993, "l", "p", 1)
        remove_account(db_conn, "to_remove")
        assert list(list_accounts(db_conn, enabled_only=False)) == []

    def test_remove_nonexistent_account_does_not_raise(self, db_conn):
        # DELETE на несуществующий ключ — не ошибка, просто 0 строк затронуто
        remove_account(db_conn, "never_existed")

    def test_remove_only_affects_target_account(self, db_conn):
        add_account(db_conn, "keep_me", "Keep", "h1", 993, "l1", "p1", 1)
        add_account(db_conn, "remove_me", "Remove", "h2", 993, "l2", "p2", 1)
        remove_account(db_conn, "remove_me")
        remaining = list_accounts(db_conn, enabled_only=False)
        assert len(remaining) == 1
        assert remaining[0]["provider_key"] == "keep_me"


class TestToggleAccount:
    def test_toggle_off(self, db_conn):
        add_account(db_conn, "acc1", "Account 1", "h", 993, "l", "p", 1)
        toggle_account(db_conn, "acc1", enabled=False)
        accounts = list_accounts(db_conn, enabled_only=False)
        assert accounts[0]["enabled"] == 0

    def test_toggle_on(self, db_conn):
        add_account(db_conn, "acc1", "Account 1", "h", 993, "l", "p", 1)
        toggle_account(db_conn, "acc1", enabled=False)
        toggle_account(db_conn, "acc1", enabled=True)
        accounts = list_accounts(db_conn, enabled_only=False)
        assert accounts[0]["enabled"] == 1

    def test_toggle_nonexistent_account_does_not_raise(self, db_conn):
        toggle_account(db_conn, "ghost", enabled=True)
