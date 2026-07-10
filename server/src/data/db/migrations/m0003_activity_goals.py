"""Phase 10.2 (Today dashboard section, see README): a new, independent
daily activity goal (steps/cardio), historized the same
create-new/deactivate-old pattern as ``goal_plans``/``engine_settings``.

This is the first purely-additive schema change to go through the
migration protocol instead of a further ``DB.SCHEMA`` edit -- establishing
that convention change (README's Phase 10.1 plan) for a brand-new table,
not just the destructive body_logs column drop m0002 handles. Still
written as ``CREATE TABLE IF NOT EXISTS``: harmless idempotency belt for a
DB that somehow already re-ran this migration's version number.
"""

from __future__ import annotations

import sqlite3

VERSION = 3

_CREATE_ACTIVITY_GOALS = """
CREATE TABLE IF NOT EXISTS activity_goals (
    activity_goal_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    steps_goal REAL,
    cardio_kcal_goal REAL,
    start_date TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
)
"""


def upgrade(conn: sqlite3.Connection) -> None:
    conn.execute(_CREATE_ACTIVITY_GOALS)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_activity_goals_user_active "
        "ON activity_goals(user_id, active)"
    )
