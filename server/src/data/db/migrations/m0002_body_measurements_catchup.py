"""Catch-up migration for Phase 9.1's ``body_logs.waist_cm``/``neck_cm``
removal (see README's Phase 10.1 section).

Phase 9.1 dropped ``waist_cm``/``neck_cm`` from ``DB.SCHEMA``'s
``body_logs`` definition in favor of the new ``body_measurements`` table,
but shipped (v4.0) before this migration protocol existed -- so a real
device that installed v4.0 (or any earlier release) still has those two
columns physically on its own ``body_logs`` table today, since
``CREATE TABLE IF NOT EXISTS`` is a no-op against a table that already
exists. This migration is the first *real* user of the protocol: it
copies any surviving ``waist_cm``/``neck_cm`` values into
``body_measurements`` (mirroring Phase 9.1's own JSON-import backfill
logic, just applied automatically instead of by hand) and then drops the
two columns -- SQLite has no ``ALTER TABLE ... DROP COLUMN`` old enough to
rely on here, so this uses the standard create-copy-drop-rename sequence
(sqlite.org's "Making Other Kinds Of Table Schema Changes" procedure):
build the *new* shape under a temporary name, copy the data across, drop
the old table, then rename the new one into place -- deliberately never
renaming ``body_logs`` itself away, so any other table's
``REFERENCES body_logs(...)`` (``metrics_snapshots.log_id``) is never
rewritten by SQLite's rename-following behavior.

A brand-new DB (or one that has already run this migration once) never
has these columns in the first place -- this is a no-op for both.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

VERSION = 2

#: body_logs' shape as of this migration (Phase 9.1's post-perimeter-split
#: columns) -- frozen here, deliberately not imported from DB.SCHEMA, since
#: a migration is a historical record of what it produced *at the time*,
#: not a pointer to whatever SCHEMA looks like by the time someone reads
#: this file later.
_CREATE_BODY_LOGS_NEW = """
CREATE TABLE body_logs_m0002_new (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    date TEXT NOT NULL,
    weight_kg REAL,
    intake_kcal REAL,
    intake_is_real INTEGER NOT NULL DEFAULT 1,
    steps REAL,
    cardio_kcal REAL NOT NULL DEFAULT 0,
    source TEXT NOT NULL DEFAULT 'real' CHECK (source IN ('real', 'projected')),
    granularity TEXT NOT NULL DEFAULT 'weekly' CHECK (granularity IN ('daily', 'weekly')),
    carbs_g REAL,
    fat_g REAL,
    protein_g REAL,
    created_at TEXT NOT NULL,
    UNIQUE(user_id, date)
)
"""

_COPY_COLUMNS = (
    "log_id, user_id, date, weight_kg, intake_kcal, intake_is_real, steps, "
    "cardio_kcal, source, granularity, carbs_g, fat_g, protein_g, created_at"
)


def upgrade(conn: sqlite3.Connection) -> None:
    columns = {row[1] for row in conn.execute("PRAGMA table_info(body_logs)")}
    if "waist_cm" not in columns and "neck_cm" not in columns:
        return  # already on the new shape -- fresh DB, or already migrated

    created_at = datetime.now(timezone.utc).isoformat()
    surviving = conn.execute(
        """
        SELECT user_id, date, waist_cm, neck_cm FROM body_logs
        WHERE waist_cm IS NOT NULL OR neck_cm IS NOT NULL
        """
    ).fetchall()
    for user_id, log_date, waist_cm, neck_cm in surviving:
        # INSERT OR IGNORE: a body_measurements row may already exist at
        # this exact (user_id, date) -- e.g. a manual Phase 9.1 JSON import
        # already recovered it -- in which case that existing row wins and
        # this backfill is a no-op for it, same "best-effort, never
        # clobbers" spirit as the existing import path.
        conn.execute(
            """
            INSERT OR IGNORE INTO body_measurements
                (user_id, date, waist_cm, neck_cm, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, log_date, waist_cm, neck_cm, created_at),
        )

    conn.execute(_CREATE_BODY_LOGS_NEW)
    conn.execute(
        f"""
        INSERT INTO body_logs_m0002_new ({_COPY_COLUMNS})
        SELECT {_COPY_COLUMNS} FROM body_logs
        """
    )
    # Rows above were copied with their original explicit log_id values,
    # which (unlike a normal AUTOINCREMENT insert) never touches
    # sqlite_sequence -- without this, a future real insert could generate
    # a log_id that collides with one of the just-copied rows. Reseed it
    # from the copied data's own max id (0/absent for an empty table,
    # AUTOINCREMENT's own "nothing inserted yet" state).
    conn.execute(
        """
        INSERT OR REPLACE INTO sqlite_sequence (name, seq)
        SELECT 'body_logs_m0002_new', COALESCE(MAX(log_id), 0) FROM body_logs_m0002_new
        """
    )
    conn.execute("DROP TABLE body_logs")
    # ALTER TABLE ... RENAME TO also renames this table's own row in
    # sqlite_sequence (SQLite's documented rename behavior), carrying the
    # reseeded counter above forward under the final "body_logs" name.
    conn.execute("ALTER TABLE body_logs_m0002_new RENAME TO body_logs")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_body_logs_user_date ON body_logs(user_id, date)")
