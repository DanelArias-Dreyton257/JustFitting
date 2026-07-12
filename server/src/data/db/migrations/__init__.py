"""Versioned DB migration protocol (Phase 10.1, see README).

Each ``mNNNN_<name>.py`` module exposes a module-level ``VERSION`` (int)
and ``upgrade(conn: sqlite3.Connection) -> None``. ``DB.__init__`` reads
``PRAGMA user_version``, applies every migration numbered above it (in
version order) inside one transaction, then advances ``PRAGMA
user_version`` to the highest version applied -- see ``DB._apply_migrations``.

From here on, a schema change is a new numbered module in this package,
not an edit to ``DB.SCHEMA`` -- SCHEMA stays frozen at the shape m0001
represents. This keeps exactly one code path (this runner) responsible
for every DB's schema, whether it's a brand-new install (starts at
version 0, applies every migration) or a real device upgrading in place
(applies only whatever is still pending) -- both converge on the same
``user_version`` and the same table shapes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List
import sqlite3

from server.src.data.db.migrations import (
    m0001_baseline,
    m0002_body_measurements_catchup,
    m0003_activity_goals,
    m0004_missing_log_alert_days,
    m0005_goal_plan_direction,
)


@dataclass(frozen=True)
class Migration:
    version: int
    upgrade: Callable[[sqlite3.Connection], None]
    name: str


def _migration(module) -> Migration:
    return Migration(version=module.VERSION, upgrade=module.upgrade, name=module.__name__)


MIGRATIONS: List[Migration] = sorted(
    [
        _migration(m0001_baseline),
        _migration(m0002_body_measurements_catchup),
        _migration(m0003_activity_goals),
        _migration(m0004_missing_log_alert_days),
        _migration(m0005_goal_plan_direction),
    ],
    key=lambda m: m.version,
)

assert len(MIGRATIONS) == len({m.version for m in MIGRATIONS}), "duplicate migration VERSION"
