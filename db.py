import sqlite3


def init_db():
    conn = sqlite3.connect("gmail_state.db")
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


# Обёртки для обратной совместимости с Gmail-частью
def get_last_history_id(conn):
    return get_state(conn, "last_history_id")


def save_last_history_id(conn, history_id):
    save_state(conn, "last_history_id", history_id)


def get_last_uid_mailru(conn):
    value = get_state(conn, "last_uid_mailru")
    return int(value) if value is not None else None


def save_last_uid_mailru(conn, uid):
    save_state(conn, "last_uid_mailru", uid)
