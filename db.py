import sqlite3
import os


def init_db():
    db_path = os.environ.get("DB_PATH", "state.db")
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row

    conn.execute("""
        CREATE TABLE IF NOT EXISTS state (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    conn.commit()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS mail_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider_key TEXT UNIQUE NOT NULL,
            display_name TEXT NOT NULL,
            host TEXT NOT NULL,
            port INTEGER NOT NULL DEFAULT 993,
            login TEXT NOT NULL,
            password TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            owner_chat_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()

    return conn


def get_state(conn, key):
    row = conn.execute("SELECT value FROM state WHERE key = ?", (key,)).fetchone()
    return row[0] if row else None


def save_state(conn, key, value):
    conn.execute(
        "INSERT OR REPLACE INTO state (key, value) VALUES (?, ?)",
        (key, str(value)),
    )
    conn.commit()


def get_last_uid(conn, name):
    value = get_state(conn, f"last_uid_{name}")
    return int(value) if value is not None else None


def save_last_uid(conn, uid, name):
    save_state(conn, f"last_uid_{name}", uid)


def add_account(
    conn, provider_key, display_name, host, port, login, password, owner_chat_id
):
    conn.execute(
        """INSERT INTO mail_accounts
           (provider_key, display_name, host, port, login, password, owner_chat_id)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (provider_key, display_name, host, port, login, password, owner_chat_id),
    )
    conn.commit()


def list_accounts(conn, enabled_only=True):
    q = "SELECT * FROM mail_accounts"
    if enabled_only:
        q += " WHERE enabled = 1"
    return conn.execute(q).fetchall()


def remove_account(conn, provider_key):
    conn.execute("DELETE FROM mail_accounts WHERE provider_key = ?", (provider_key,))
    conn.commit()


def toggle_account(conn, provider_key, enabled: bool):
    conn.execute(
        "UPDATE mail_accounts SET enabled = ? WHERE provider_key = ?",
        (int(enabled), provider_key),
    )
    conn.commit()
