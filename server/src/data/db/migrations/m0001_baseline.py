"""Baseline marker (Phase 10.1, see README).

Version 1 represents whatever ``DB.SCHEMA``'s ``CREATE TABLE IF NOT
EXISTS``/``CREATE INDEX IF NOT EXISTS`` statements produce as of this
phase -- ``DB.__init__`` still runs that script unconditionally on every
boot, before any migration, so a brand-new DB (dev machine, fresh Android
install, a fresh Render deploy) already has this shape without this
migration doing anything. This module exists purely so version 1 is a
well-defined number for m0002+ to build on, and so an existing DB (already
at this shape, whatever its literal ``user_version`` was before this phase
shipped) converges on the same ``user_version`` a fresh install lands on.

From this phase on, a schema change is a new numbered migration module,
not a further edit to ``SCHEMA`` -- see m0003_activity_goals.py for the
first purely-additive example (a brand-new table), and
m0002_body_measurements_catchup.py for the first destructive one (a
column drop SQLite can't express as an idempotent ``ALTER TABLE``).
"""

from __future__ import annotations

import sqlite3

VERSION = 1


def upgrade(conn: sqlite3.Connection) -> None:
    pass
