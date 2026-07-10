"""SQLite connection wrapper.

``SCHEMA`` below is the idempotent ``CREATE TABLE IF NOT EXISTS``/
``CREATE INDEX IF NOT EXISTS`` baseline every DB gets on every connect --
it's frozen at the shape ``server/src/data/db/migrations/m0001_baseline.py``
represents and is no longer where a schema change goes (Phase 10.1, see
README). Real accounts now have real on-device data (Android's embedded
server, Phase 6) that a schema change must carry forward correctly, not
just recreate -- so from this phase on, a schema change is a new numbered
module in ``data/db/migrations/`` (``upgrade(conn) -> None``), applied by
``_apply_migrations`` below via SQLite's own ``PRAGMA user_version``, never
a further edit to ``SCHEMA`` itself. This applies to purely-additive
changes too (a new table), not just destructive ones (a column drop) --
see ``migrations/__init__.py``'s own docstring for why one linear list is
better than two divergent code paths.

Local dev may still delete-and-recreate for convenience
(``scripts/reset_db.sh`` + ``scripts/seed_demo_data.sh``) -- that's just a
fresh DB starting at ``user_version=0`` and running every migration in
order, same as a first-ever install. A real device's DB always migrates in
place; it's never reset.
"""

from __future__ import annotations

import sqlite3
import threading
from typing import List

from server.src.data.db.migrations import MIGRATIONS

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    height_cm REAL NOT NULL,
    sex INTEGER NOT NULL CHECK (sex IN (0, 1)),
    birthdate TEXT NOT NULL,
    units TEXT NOT NULL DEFAULT 'metric',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);

CREATE TABLE IF NOT EXISTS body_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    date TEXT NOT NULL,
    -- Phase 7.4 (partial logs & independent-source merging, see README):
    -- nullable, not NOT NULL -- NULL means "not logged yet by any
    -- source" (sync, manual entry, or import), not zero. A row can be
    -- partial (e.g. steps-only from a Mi Fitness sync) and gets
    -- completed later by merging in whatever's still missing
    -- (LogManager.upsert_fields / PUT /api/logs/by-date, or an ordinary
    -- edit). The engine only ever computes a row once weight/intake/steps
    -- are present and a body_measurements row can supply waist/neck --
    -- see CompositionEngine.compute_row's completeness guard and
    -- MetricsSeriesService's incomplete-week filtering. Phase 9.1: waist_cm
    -- and neck_cm moved off this table entirely -- see body_measurements
    -- below.
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
);
CREATE INDEX IF NOT EXISTS idx_body_logs_user_date ON body_logs(user_id, date);

-- Phase 9.1 (body composition logging separation, see README): perimeters
-- are a sporadically-logged record, decoupled from body_logs' weight/
-- nutrition/steps cadence -- "static" from one measurement to the next for
-- every computation in between (BodyMeasurementManager.get_effective).
-- Phase 9.3 adds nine more record-only columns, never read by the engine.
CREATE TABLE IF NOT EXISTS body_measurements (
    measurement_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    date TEXT NOT NULL,
    waist_cm REAL,
    neck_cm REAL,
    shoulder_cm REAL,
    chest_cm REAL,
    hips_cm REAL,
    biceps_r_cm REAL,
    biceps_l_cm REAL,
    thigh_r_cm REAL,
    thigh_l_cm REAL,
    calf_r_cm REAL,
    calf_l_cm REAL,
    created_at TEXT NOT NULL,
    UNIQUE(user_id, date)
);
CREATE INDEX IF NOT EXISTS idx_body_measurements_user_date ON body_measurements(user_id, date);

CREATE TABLE IF NOT EXISTS goal_plans (
    goal_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    target_bf REAL NOT NULL,
    weekly_rate REAL NOT NULL,
    start_date TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_goal_plans_user_active ON goal_plans(user_id, active);

CREATE TABLE IF NOT EXISTS audit_log (
    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    field TEXT NOT NULL,
    previous_value TEXT,
    new_value TEXT,
    changed_at TEXT NOT NULL,
    engine_version INTEGER
);
CREATE INDEX IF NOT EXISTS idx_audit_log_user ON audit_log(user_id, changed_at);

CREATE TABLE IF NOT EXISTS metrics_snapshots (
    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    log_id INTEGER NOT NULL REFERENCES body_logs(log_id) ON DELETE CASCADE,
    engine_version INTEGER NOT NULL,
    date TEXT NOT NULL,
    age INTEGER NOT NULL,
    bmi REAL NOT NULL,
    ffmi REAL NOT NULL,
    ffmi_adj REAL NOT NULL,
    rfm REAL NOT NULL,
    navy REAL NOT NULL,
    deurenberg REAL NOT NULL,
    body_fat REAL NOT NULL,
    fat_mass_kg REAL NOT NULL,
    lean_mass_kg REAL NOT NULL,
    above_target REAL NOT NULL,
    bmr REAL NOT NULL,
    neat REAL NOT NULL,
    tdee REAL NOT NULL,
    target_calories REAL NOT NULL,
    intake_diff REAL NOT NULL,
    tef_kcal REAL NOT NULL DEFAULT 0,
    tef_mode TEXT NOT NULL DEFAULT 'flat',
    weight_delta_kg REAL NOT NULL,
    weight_delta_pct REAL NOT NULL,
    weight_objective_kg REAL NOT NULL,
    weight_gap_kg REAL NOT NULL,
    weight_to_shed_kg REAL NOT NULL,
    weekly_deficit_kcal REAL NOT NULL,
    daily_deficit_kcal REAL NOT NULL,
    final_weight_kg REAL NOT NULL,
    weeks_to_goal REAL NOT NULL,
    source TEXT NOT NULL,
    computed_at TEXT NOT NULL,
    UNIQUE(log_id, engine_version)
);
CREATE INDEX IF NOT EXISTS idx_metrics_snapshots_log ON metrics_snapshots(log_id);

CREATE TABLE IF NOT EXISTS projections (
    projection_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    run_id TEXT NOT NULL,
    projected_date TEXT NOT NULL,
    estimated_weight REAL NOT NULL,
    estimated_waist REAL NOT NULL,
    estimated_neck REAL NOT NULL,
    source_model TEXT NOT NULL,
    base_regression TEXT NOT NULL,
    activity_model TEXT NOT NULL DEFAULT 'constant',
    trend_model TEXT NOT NULL DEFAULT 'ols',
    generated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_projections_user_run ON projections(user_id, run_id);

CREATE TABLE IF NOT EXISTS alert_log (
    alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    type TEXT NOT NULL,
    severity TEXT NOT NULL,
    date TEXT NOT NULL,
    message TEXT NOT NULL,
    value REAL NOT NULL,
    threshold REAL NOT NULL,
    detected_at TEXT NOT NULL,
    acknowledged_at TEXT,
    UNIQUE(user_id, type, date)
);
CREATE INDEX IF NOT EXISTS idx_alert_log_user ON alert_log(user_id, date);

CREATE TABLE IF NOT EXISTS engine_settings (
    settings_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    tef REAL NOT NULL,
    kcal_per_kg_fat REAL NOT NULL,
    neat_step_factor REAL NOT NULL,
    implausible_weekly_change_pct REAL NOT NULL,
    stagnation_weeks INTEGER NOT NULL,
    stagnation_threshold_kg REAL NOT NULL,
    lean_loss_window_weeks INTEGER NOT NULL,
    max_lean_mass_loss_share REAL NOT NULL,
    significant_deviation_kg REAL NOT NULL,
    bmr_model TEXT NOT NULL DEFAULT 'cunningham',
    w_rfm REAL NOT NULL DEFAULT 0.50,
    w_navy REAL NOT NULL DEFAULT 0.25,
    w_deur REAL NOT NULL DEFAULT 0.25,
    delta REAL NOT NULL DEFAULT 0.0,
    ffmi_coef REAL NOT NULL DEFAULT 6.3,
    lean_tissue_kcal_per_kg REAL NOT NULL DEFAULT 2100.0,
    fat_ratio_ideal REAL NOT NULL DEFAULT 0.25,
    reconciliation_error_threshold_kcal REAL NOT NULL DEFAULT 300.0,
    tef_mode TEXT NOT NULL DEFAULT 'flat',
    kappa_carbs REAL NOT NULL DEFAULT 0.300,
    kappa_fat REAL NOT NULL DEFAULT 0.135,
    kappa_protein REAL NOT NULL DEFAULT 1.000,
    macro_kcal_mismatch_pct REAL NOT NULL DEFAULT 0.15,
    protein_target_g_per_kg REAL NOT NULL DEFAULT 1.75,
    fat_target_g_per_kg REAL NOT NULL DEFAULT 0.70,
    macro_target_deviation_pct REAL NOT NULL DEFAULT 0.20,
    start_date TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_engine_settings_user_active ON engine_settings(user_id, active);
"""


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
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()
            self._apply_migrations()
            self._conn.execute("PRAGMA foreign_keys = ON")
            self._conn.commit()

    def _apply_migrations(self) -> None:
        """Applies every migration numbered above the DB's current
        ``PRAGMA user_version`` (see ``migrations/__init__.py``), inside one
        transaction so a failure never leaves a half-migrated file -- either
        every pending migration lands and ``user_version`` advances to the
        highest one applied, or none of them do and the DB is left exactly
        as it was.

        Foreign-key enforcement is switched off for the duration: SQLite's
        own recommended procedure for a schema change ``ALTER TABLE`` can't
        express directly (e.g. m0002's column drop, a create-copy-drop-
        rename sequence) needs it off, and ``PRAGMA foreign_keys`` is a
        documented no-op once a transaction is already open -- so this must
        happen before ``BEGIN``, not inside a migration's own ``upgrade()``.
        """
        current_version = self._conn.execute("PRAGMA user_version").fetchone()[0]
        pending = [m for m in MIGRATIONS if m.version > current_version]
        if not pending:
            return

        self._conn.execute("PRAGMA foreign_keys = OFF")
        self._conn.execute("BEGIN")
        try:
            for migration in pending:
                migration.upgrade(self._conn)
                self._conn.execute(f"PRAGMA user_version = {migration.version}")
            violations = self._conn.execute("PRAGMA foreign_key_check").fetchall()
            if violations:
                raise RuntimeError(
                    f"migration(s) {[m.name for m in pending]} left dangling "
                    f"foreign keys: {[tuple(row) for row in violations]}"
                )
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    @property
    def connection(self) -> sqlite3.Connection:
        return self._conn

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
