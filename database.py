import os
import sqlite3
from contextlib import contextmanager

DB_PATH = os.getenv("DB_PATH", "games.db")


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS stats (
                user_id INTEGER,
                game TEXT,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                draws INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, game)
            )
        """)


def upsert_user(user_id, username, first_name):
    with get_db() as conn:
        conn.execute("""
            INSERT INTO users (user_id, username, first_name)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username=excluded.username,
                first_name=excluded.first_name
        """, (user_id, username, first_name))


def record_result(user_id, game, result):
    # result: 'win' | 'loss' | 'draw'
    col = {"win": "wins", "loss": "losses", "draw": "draws"}[result]
    with get_db() as conn:
        conn.execute(f"""
            INSERT INTO stats (user_id, game, {col})
            VALUES (?, ?, 1)
            ON CONFLICT(user_id, game) DO UPDATE SET {col} = {col} + 1
        """, (user_id, game))


def get_stats(user_id, game=None):
    with get_db() as conn:
        if game:
            row = conn.execute(
                "SELECT * FROM stats WHERE user_id=? AND game=?", (user_id, game)
            ).fetchone()
            return dict(row) if row else {"wins": 0, "losses": 0, "draws": 0}
        rows = conn.execute(
            "SELECT * FROM stats WHERE user_id=?", (user_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_leaderboard(game, limit=10):
    with get_db() as conn:
        rows = conn.execute("""
            SELECT s.user_id, u.username, u.first_name, s.wins, s.losses, s.draws,
                   (s.wins - s.losses) as score
            FROM stats s JOIN users u ON u.user_id = s.user_id
            WHERE s.game = ?
            ORDER BY score DESC, s.wins DESC
            LIMIT ?
        """, (game, limit)).fetchall()
        return [dict(r) for r in rows]
