"""Phase 12.1 (goal-type-aware trajectory model, see README): adds an
explicit, stored ``direction`` column to ``goal_plans``, replacing
``GoalPlan.direction``'s previous sign-derived ``@property``. Every
existing row backfills the same value the old derived property would
have produced, so this migration is a pure storage change, not a
behavior change for any already-existing goal.
"""

from __future__ import annotations

import sqlite3

VERSION = 5


def upgrade(conn: sqlite3.Connection) -> None:
    columns = {row[1] for row in conn.execute("PRAGMA table_info(goal_plans)")}
    if "direction" not in columns:
        conn.execute(
            "ALTER TABLE goal_plans ADD COLUMN direction TEXT NOT NULL "
            "DEFAULT 'cut' CHECK (direction IN ('cut', 'bulk'))"
        )
        conn.execute("UPDATE goal_plans SET direction = 'bulk' WHERE weekly_rate > 0")
