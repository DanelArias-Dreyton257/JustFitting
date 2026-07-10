"""Phase 11.3 (missing-log alert, see README): adds a per-account-overridable
``missing_log_alert_days`` threshold to ``engine_settings``, the same
historized settings table as every other alert threshold (e.g.
``reconciliation_error_threshold_kcal``).

Purely additive, so unlike m0002's create-copy-drop-rename dance (only
needed for a column *drop*), a plain ``ADD COLUMN ... DEFAULT`` is enough.
"""

from __future__ import annotations

import sqlite3

VERSION = 4


def upgrade(conn: sqlite3.Connection) -> None:
    columns = {row[1] for row in conn.execute("PRAGMA table_info(engine_settings)")}
    if "missing_log_alert_days" not in columns:
        conn.execute(
            "ALTER TABLE engine_settings "
            "ADD COLUMN missing_log_alert_days REAL NOT NULL DEFAULT 7.0"
        )
