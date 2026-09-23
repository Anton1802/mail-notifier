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


def get_last_history_id(conn):
    row = conn.execute(
        "SELECT value FROM state WHERE key = ?", ("last_history_id",)
    ).fetchone()
    return row[0] if row else None


def save_last_history_id(conn, history_id):
    conn.execute(
        "INSERT OR REPLACE INTO state (key, value) VALUES (?, ?)",
        ("last_history_id", str(history_id)),
    )
    conn.commit()
