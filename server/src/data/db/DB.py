"""SQLite connection wrapper with a linear, versioned migration runner.

Migrations are plain SQL scripts applied in order and tracked with
``PRAGMA user_version``, so booting the server against an existing database
always brings it up to the latest schema (see scripts/update.sh).
"""

from __future__ import annotations

import sqlite3
import threading
from typing import List, Tuple

MIGRATIONS: List[Tuple[int, str]] = [
    (
        1,
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            height_cm REAL NOT NULL,
            sex INTEGER NOT NULL CHECK (sex IN (0, 1)),
            birthdate TEXT NOT NULL,
            target_bf REAL NOT NULL,
            weekly_rate REAL NOT NULL,
            units TEXT NOT NULL DEFAULT 'metric',
            created_at TEXT NOT NULL
        );
        """,
    ),
    (
        2,
        """
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
        """,
    ),
    (
        3,
        """
        CREATE TABLE IF NOT EXISTS body_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
            date TEXT NOT NULL,
            weight_kg REAL NOT NULL,
            waist_cm REAL NOT NULL,
            neck_cm REAL NOT NULL,
            intake_kcal REAL NOT NULL,
            intake_is_real INTEGER NOT NULL DEFAULT 1,
            steps REAL NOT NULL,
            source TEXT NOT NULL DEFAULT 'real' CHECK (source IN ('real', 'projected')),
            created_at TEXT NOT NULL,
            UNIQUE(user_id, date)
        );
        CREATE INDEX IF NOT EXISTS idx_body_logs_user_date ON body_logs(user_id, date);
        """,
    ),
]


class DB:
    """Thin wrapper around a single sqlite3 connection for this process.

    ``check_same_thread=False`` only disables Python's same-thread guard;
    it does not make the underlying connection safe for concurrent access.
    Flask's dev server, waitress and gunicorn can all dispatch requests to
    worker threads sharing this one connection, so every access goes
    through ``self._lock``.
    """

    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self.migrate()

    @property
    def connection(self) -> sqlite3.Connection:
        return self._conn

    def migrate(self) -> None:
        with self._lock:
            current = self._conn.execute("PRAGMA user_version").fetchone()[0]
            for version, sql in MIGRATIONS:
                if version > current:
                    self._conn.executescript(sql)
                    self._conn.execute(f"PRAGMA user_version = {version}")
            self._conn.commit()

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            cursor = self._conn.execute(sql, params)
            self._conn.commit()
            return cursor

    def query(self, sql: str, params: tuple = ()) -> List[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    def query_one(self, sql: str, params: tuple = ()):
        with self._lock:
            return self._conn.execute(sql, params).fetchone()

    def close(self) -> None:
        with self._lock:
            self._conn.close()
