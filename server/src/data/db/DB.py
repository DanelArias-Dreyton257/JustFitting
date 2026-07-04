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
    (
        4,
        """
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

        INSERT INTO goal_plans (user_id, target_bf, weekly_rate, start_date, active, created_at)
        SELECT user_id, target_bf, weekly_rate, substr(created_at, 1, 10), 1, created_at
        FROM users;

        ALTER TABLE users DROP COLUMN target_bf;
        ALTER TABLE users DROP COLUMN weekly_rate;
        """,
    ),
    (
        5,
        """
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
        """,
    ),
    (
        6,
        """
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
        """,
    ),
    (
        7,
        """
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
            generated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_projections_user_run ON projections(user_id, run_id);
        """,
    ),
    (
        8,
        """
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
        """,
    ),
    (
        9,
        """
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
            start_date TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_engine_settings_user_active ON engine_settings(user_id, active);
        """,
    ),
    (
        10,
        """
        ALTER TABLE projections ADD COLUMN activity_model TEXT NOT NULL DEFAULT 'constant';
        """,
    ),
    (
        11,
        """
        ALTER TABLE projections ADD COLUMN trend_model TEXT NOT NULL DEFAULT 'ols';
        """,
    ),
    (
        12,
        """
        ALTER TABLE engine_settings ADD COLUMN bmr_model TEXT NOT NULL DEFAULT 'cunningham';
        ALTER TABLE engine_settings ADD COLUMN w_rfm REAL NOT NULL DEFAULT 0.50;
        ALTER TABLE engine_settings ADD COLUMN w_navy REAL NOT NULL DEFAULT 0.25;
        ALTER TABLE engine_settings ADD COLUMN w_deur REAL NOT NULL DEFAULT 0.25;
        ALTER TABLE engine_settings ADD COLUMN delta REAL NOT NULL DEFAULT 0.0;
        ALTER TABLE engine_settings ADD COLUMN ffmi_coef REAL NOT NULL DEFAULT 6.3;
        ALTER TABLE engine_settings ADD COLUMN lean_tissue_kcal_per_kg REAL NOT NULL DEFAULT 2100.0;
        ALTER TABLE engine_settings ADD COLUMN fat_ratio_ideal REAL NOT NULL DEFAULT 0.25;
        """,
    ),
    (
        13,
        """
        ALTER TABLE body_logs ADD COLUMN cardio_kcal REAL NOT NULL DEFAULT 0;
        """,
    ),
    (
        14,
        """
        ALTER TABLE engine_settings ADD COLUMN reconciliation_error_threshold_kcal REAL NOT NULL DEFAULT 300.0;
        """,
    ),
    (
        15,
        """
        ALTER TABLE body_logs ADD COLUMN granularity TEXT NOT NULL DEFAULT 'weekly' CHECK (granularity IN ('daily', 'weekly'));
        """,
    ),
    (
        16,
        """
        ALTER TABLE body_logs ADD COLUMN carbs_g REAL;
        ALTER TABLE body_logs ADD COLUMN fat_g REAL;
        ALTER TABLE body_logs ADD COLUMN protein_g REAL;
        """,
    ),
    (
        17,
        """
        ALTER TABLE engine_settings ADD COLUMN tef_mode TEXT NOT NULL DEFAULT 'flat';
        ALTER TABLE engine_settings ADD COLUMN kappa_carbs REAL NOT NULL DEFAULT 0.300;
        ALTER TABLE engine_settings ADD COLUMN kappa_fat REAL NOT NULL DEFAULT 0.135;
        ALTER TABLE engine_settings ADD COLUMN kappa_protein REAL NOT NULL DEFAULT 1.000;
        ALTER TABLE engine_settings ADD COLUMN macro_kcal_mismatch_pct REAL NOT NULL DEFAULT 0.15;
        """,
    ),
    (
        18,
        """
        ALTER TABLE metrics_snapshots ADD COLUMN tef_kcal REAL NOT NULL DEFAULT 0;
        ALTER TABLE metrics_snapshots ADD COLUMN tef_mode TEXT NOT NULL DEFAULT 'flat';
        """,
    ),
    (
        19,
        """
        ALTER TABLE engine_settings ADD COLUMN protein_target_g_per_kg REAL NOT NULL DEFAULT 1.75;
        ALTER TABLE engine_settings ADD COLUMN fat_target_g_per_kg REAL NOT NULL DEFAULT 0.70;
        ALTER TABLE engine_settings ADD COLUMN macro_target_deviation_pct REAL NOT NULL DEFAULT 0.20;
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
