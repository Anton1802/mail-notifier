import sqlite3
import os


def init_db():
    db_path = os.environ.get("DB_PATH", "state.db")
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS state (
            key TEXT PRIMARY KEY,
            value TEXT
        )
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
