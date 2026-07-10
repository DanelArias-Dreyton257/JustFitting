import os
import sqlite3
import tempfile
import threading
import unittest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

from server.src.data.db import DB as DBModule
from server.src.data.db.BodyLogDAO import BodyLogDAO
from server.src.data.db.BodyMeasurementDAO import BodyMeasurementDAO
from server.src.data.db.DB import DB
from server.src.data.db.GoalPlanDAO import GoalPlanDAO
from server.src.data.db.migrations import MIGRATIONS, Migration
from server.src.data.db.SessionDAO import SessionDAO
from server.src.data.db.UserDAO import UserDAO


class DBTestCase(unittest.TestCase):
    def setUp(self):
        self.db = DB(":memory:")

    def tearDown(self):
        self.db.close()

    def test_schema_is_idempotent_across_reconnects(self):
        """Re-running SCHEMA against an already-initialized database (the
        normal case on every boot) must not error or lose data."""
        UserDAO(self.db).create(
            username="demo_cut",
            email="demo_cut@example.com",
            password_hash="hash",
            height_cm=176,
            sex=1,
            birthdate=date(2001, 8, 22),
        )
        self.db._conn.executescript(DBModule.SCHEMA)
        row = self.db.query_one("SELECT COUNT(*) AS count FROM users")
        self.assertEqual(row["count"], 1)

    def test_user_dao_crud(self):
        dao = UserDAO(self.db)
        profile = dao.create(
            username="demo_cut",
            email="demo_cut@example.com",
            password_hash="hash",
            height_cm=176,
            sex=1,
            birthdate=date(2001, 8, 22),
        )
        self.assertIsNotNone(profile.user_id)

        by_username = dao.get_by_username("demo_cut")
        self.assertEqual(by_username.user_id, profile.user_id)

        by_email = dao.get_by_email("demo_cut@example.com")
        self.assertEqual(by_email.user_id, profile.user_id)

        updated = dao.update(profile.user_id, height_cm=177)
        self.assertEqual(updated.height_cm, 177)

        dao.delete(profile.user_id)
        self.assertIsNone(dao.get_by_id(profile.user_id))

    def test_user_unique_constraints(self):
        dao = UserDAO(self.db)
        dao.create(
            username="demo_cut",
            email="demo_cut@example.com",
            password_hash="hash",
            height_cm=176,
            sex=1,
            birthdate=date(2001, 8, 22),
        )
        with self.assertRaises(Exception):
            dao.create(
                username="demo_cut",
                email="other@example.com",
                password_hash="hash",
                height_cm=176,
                sex=1,
                birthdate=date(2001, 8, 22),
            )

    def test_session_dao_lifecycle(self):
        user_dao = UserDAO(self.db)
        session_dao = SessionDAO(self.db)
        profile = user_dao.create(
            username="demo_cut",
            email="demo_cut@example.com",
            password_hash="hash",
            height_cm=176,
            sex=1,
            birthdate=date(2001, 8, 22),
        )
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)
        session_dao.create("token-123", profile.user_id, expires_at)

        row = session_dao.get("token-123")
        self.assertEqual(row["user_id"], profile.user_id)

        session_dao.delete("token-123")
        self.assertIsNone(session_dao.get("token-123"))

    def test_session_dao_deletes_expired(self):
        user_dao = UserDAO(self.db)
        session_dao = SessionDAO(self.db)
        profile = user_dao.create(
            username="demo_cut",
            email="demo_cut@example.com",
            password_hash="hash",
            height_cm=176,
            sex=1,
            birthdate=date(2001, 8, 22),
        )
        session_dao.create(
            "expired", profile.user_id, datetime.now(timezone.utc) - timedelta(days=1)
        )
        session_dao.create(
            "active", profile.user_id, datetime.now(timezone.utc) + timedelta(days=1)
        )

        session_dao.delete_expired(datetime.now(timezone.utc))

        self.assertIsNone(session_dao.get("expired"))
        self.assertIsNotNone(session_dao.get("active"))

    def test_body_log_dao_crud_and_unique_per_user_date(self):
        user_dao = UserDAO(self.db)
        log_dao = BodyLogDAO(self.db)
        profile = user_dao.create(
            username="demo_cut",
            email="demo_cut@example.com",
            password_hash="hash",
            height_cm=176,
            sex=1,
            birthdate=date(2001, 8, 22),
        )
        log = log_dao.create(
            user_id=profile.user_id,
            date=date(2026, 6, 26),
            weight_kg=90.7,
            intake_kcal=2014.30,
            intake_is_real=True,
            steps=5000,
        )
        self.assertEqual(log.source, "real")

        fetched = log_dao.get_by_user_and_date(profile.user_id, date(2026, 6, 26))
        self.assertEqual(fetched.log_id, log.log_id)

        with self.assertRaises(Exception):
            log_dao.create(
                user_id=profile.user_id,
                date=date(2026, 6, 26),
                weight_kg=91.0,
                intake_kcal=2000,
                intake_is_real=True,
                steps=5000,
            )

        updated = log_dao.update(log.log_id, weight_kg=90.5)
        self.assertAlmostEqual(updated.weight_kg, 90.5)

        logs = log_dao.list_for_user(profile.user_id)
        self.assertEqual(len(logs), 1)

        log_dao.delete(log.log_id)
        self.assertIsNone(log_dao.get_by_id(log.log_id))

    def test_body_logs_cascade_delete_with_user(self):
        user_dao = UserDAO(self.db)
        log_dao = BodyLogDAO(self.db)
        profile = user_dao.create(
            username="demo_cut",
            email="demo_cut@example.com",
            password_hash="hash",
            height_cm=176,
            sex=1,
            birthdate=date(2001, 8, 22),
        )
        log_dao.create(
            user_id=profile.user_id,
            date=date(2026, 6, 26),
            weight_kg=90.7,
            intake_kcal=2014.30,
            intake_is_real=True,
            steps=5000,
        )
        user_dao.delete(profile.user_id)
        self.assertEqual(log_dao.list_for_user(profile.user_id), [])

    def test_body_measurement_dao_crud_and_get_effective(self):
        user_dao = UserDAO(self.db)
        measurement_dao = BodyMeasurementDAO(self.db)
        profile = user_dao.create(
            username="demo_cut",
            email="demo_cut@example.com",
            password_hash="hash",
            height_cm=176,
            sex=1,
            birthdate=date(2001, 8, 22),
        )
        first = measurement_dao.create(
            user_id=profile.user_id, date=date(2026, 1, 1), waist_cm=91.0, neck_cm=38.5
        )
        second = measurement_dao.create(
            user_id=profile.user_id, date=date(2026, 3, 1), waist_cm=85.0, neck_cm=37.0
        )

        with self.assertRaises(Exception):
            measurement_dao.create(user_id=profile.user_id, date=date(2026, 1, 1), waist_cm=90.0)

        # "static until next update": before the first measurement there's
        # nothing to resolve; between the two, the first one still applies;
        # on/after the second, the second applies.
        self.assertIsNone(measurement_dao.get_effective(profile.user_id, date(2025, 12, 31)))
        effective_mid = measurement_dao.get_effective(profile.user_id, date(2026, 2, 1))
        self.assertEqual(effective_mid.measurement_id, first.measurement_id)
        effective_after = measurement_dao.get_effective(profile.user_id, date(2026, 6, 1))
        self.assertEqual(effective_after.measurement_id, second.measurement_id)

        updated = measurement_dao.update(second.measurement_id, waist_cm=84.0)
        self.assertAlmostEqual(updated.waist_cm, 84.0)

        measurement_dao.delete(first.measurement_id)
        self.assertEqual(len(measurement_dao.list_for_user(profile.user_id)), 1)

    def test_body_measurements_cascade_delete_with_user(self):
        user_dao = UserDAO(self.db)
        measurement_dao = BodyMeasurementDAO(self.db)
        profile = user_dao.create(
            username="demo_cut",
            email="demo_cut@example.com",
            password_hash="hash",
            height_cm=176,
            sex=1,
            birthdate=date(2001, 8, 22),
        )
        measurement_dao.create(user_id=profile.user_id, date=date(2026, 1, 1), waist_cm=91.0)
        user_dao.delete(profile.user_id)
        self.assertEqual(measurement_dao.list_for_user(profile.user_id), [])

    def test_goal_plan_dao_history_and_deactivate(self):
        user_dao = UserDAO(self.db)
        goal_dao = GoalPlanDAO(self.db)
        profile = user_dao.create(
            username="demo_cut",
            email="demo_cut@example.com",
            password_hash="hash",
            height_cm=176,
            sex=1,
            birthdate=date(2001, 8, 22),
        )
        first = goal_dao.create(
            user_id=profile.user_id,
            target_bf=0.15,
            weekly_rate=-0.005,
            start_date=date(2026, 1, 1),
        )
        self.assertTrue(goal_dao.get_active(profile.user_id).goal_id == first.goal_id)

        goal_dao.deactivate(first.goal_id)
        second = goal_dao.create(
            user_id=profile.user_id,
            target_bf=0.18,
            weekly_rate=-0.004,
            start_date=date(2026, 2, 1),
        )
        active = goal_dao.get_active(profile.user_id)
        self.assertEqual(active.goal_id, second.goal_id)

        history = goal_dao.list_for_user(profile.user_id)
        self.assertEqual([g.goal_id for g in history], [second.goal_id, first.goal_id])


class MigrationRunnerTest(unittest.TestCase):
    """Phase 10.1 (versioned DB migration protocol, see README)."""

    def test_fresh_db_lands_on_latest_user_version_and_shape(self):
        """A brand-new DB (user_version starts at 0) applies every
        migration in order and converges on the exact same shape a real
        device migrating in place does (the other tests below)."""
        db = DB(":memory:")
        try:
            self.assertEqual(
                db.query_one("PRAGMA user_version")[0], MIGRATIONS[-1].version
            )
            body_log_columns = {row["name"] for row in db.query("PRAGMA table_info(body_logs)")}
            self.assertNotIn("waist_cm", body_log_columns)
            self.assertNotIn("neck_cm", body_log_columns)
            activity_goal_columns = {
                row["name"] for row in db.query("PRAGMA table_info(activity_goals)")
            }
            self.assertEqual(
                activity_goal_columns,
                {
                    "activity_goal_id",
                    "user_id",
                    "steps_goal",
                    "cardio_kcal_goal",
                    "start_date",
                    "active",
                    "created_at",
                },
            )
            engine_settings_columns = {
                row["name"] for row in db.query("PRAGMA table_info(engine_settings)")
            }
            self.assertIn("missing_log_alert_days", engine_settings_columns)
        finally:
            db.close()

    def test_reconnecting_a_migrated_db_is_a_no_op(self):
        """Applying the migrations a second time (a normal reboot) must not
        error or reset user_version."""
        path = tempfile.mktemp(suffix=".db")
        try:
            DB(path).close()
            db = DB(path)
            try:
                self.assertEqual(
                    db.query_one("PRAGMA user_version")[0], MIGRATIONS[-1].version
                )
            finally:
                db.close()
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_body_logs_waist_neck_catchup_backfills_and_drops_columns(self):
        """Reproduces a real device that installed a pre-Phase-10.1 release
        (waist_cm/neck_cm still physically on body_logs, user_version=0):
        the m0002 catch-up migration must backfill surviving values into
        body_measurements, drop the two columns, preserve every other
        table's foreign-key reference across the table rebuild, and keep
        AUTOINCREMENT from colliding with the copied rows' own ids."""
        path = tempfile.mktemp(suffix=".db")
        try:
            legacy_conn = sqlite3.connect(path)
            legacy_conn.executescript(
                """
                CREATE TABLE users (
                    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    height_cm REAL NOT NULL,
                    sex INTEGER NOT NULL,
                    birthdate TEXT NOT NULL,
                    units TEXT NOT NULL DEFAULT 'metric',
                    created_at TEXT NOT NULL
                );
                CREATE TABLE body_logs (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                    date TEXT NOT NULL,
                    weight_kg REAL,
                    waist_cm REAL,
                    neck_cm REAL,
                    intake_kcal REAL,
                    intake_is_real INTEGER NOT NULL DEFAULT 1,
                    steps REAL,
                    cardio_kcal REAL NOT NULL DEFAULT 0,
                    source TEXT NOT NULL DEFAULT 'real',
                    granularity TEXT NOT NULL DEFAULT 'weekly',
                    carbs_g REAL, fat_g REAL, protein_g REAL,
                    created_at TEXT NOT NULL,
                    UNIQUE(user_id, date)
                );
                CREATE TABLE body_measurements (
                    measurement_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                    date TEXT NOT NULL,
                    waist_cm REAL, neck_cm REAL,
                    shoulder_cm REAL, chest_cm REAL, hips_cm REAL,
                    biceps_r_cm REAL, biceps_l_cm REAL,
                    thigh_r_cm REAL, thigh_l_cm REAL,
                    calf_r_cm REAL, calf_l_cm REAL,
                    created_at TEXT NOT NULL,
                    UNIQUE(user_id, date)
                );
                CREATE TABLE metrics_snapshots (
                    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    log_id INTEGER NOT NULL REFERENCES body_logs(log_id) ON DELETE CASCADE,
                    note TEXT
                );
                """
            )
            now = datetime.now(timezone.utc).isoformat()
            legacy_conn.execute(
                "INSERT INTO users (user_id, username, email, password_hash, height_cm, "
                "sex, birthdate, created_at) VALUES (1, 'demo', 'demo@example.com', 'x', "
                "176, 1, '2001-08-22', ?)",
                (now,),
            )
            legacy_conn.execute(
                "INSERT INTO body_logs (log_id, user_id, date, weight_kg, waist_cm, "
                "neck_cm, intake_kcal, steps, created_at) VALUES "
                "(1, 1, '2026-01-01', 90.0, 91.0, 38.5, 2000, 5000, ?)",
                (now,),
            )
            legacy_conn.execute(
                "INSERT INTO body_logs (log_id, user_id, date, weight_kg, waist_cm, "
                "neck_cm, intake_kcal, steps, created_at) VALUES "
                "(2, 1, '2026-01-08', 89.5, NULL, NULL, 2000, 5000, ?)",
                (now,),
            )
            # A body_measurements row already exists at log 1's own date
            # (e.g. a manual Phase 9.1 JSON-import recovery) -- the
            # automatic backfill below must not clobber it.
            legacy_conn.execute(
                "INSERT INTO body_measurements (user_id, date, waist_cm, neck_cm, "
                "created_at) VALUES (1, '2026-01-01', 999.0, 999.0, ?)",
                (now,),
            )
            legacy_conn.execute(
                "INSERT INTO metrics_snapshots (log_id, note) VALUES (1, 'existing')"
            )
            legacy_conn.commit()
            legacy_conn.close()

            db = DB(path)
            try:
                columns = {row["name"] for row in db.query("PRAGMA table_info(body_logs)")}
                self.assertNotIn("waist_cm", columns)
                self.assertNotIn("neck_cm", columns)

                logs = db.query("SELECT log_id, date, weight_kg FROM body_logs ORDER BY log_id")
                self.assertEqual([row["log_id"] for row in logs], [1, 2])

                measurements = db.query(
                    "SELECT date, waist_cm, neck_cm FROM body_measurements ORDER BY date"
                )
                self.assertEqual(len(measurements), 1)
                # The pre-existing row wins -- never overwritten by the
                # automatic body_logs backfill (which would have written
                # 91.0/38.5 instead).
                self.assertEqual(measurements[0]["waist_cm"], 999.0)

                snapshot = db.query_one("SELECT log_id FROM metrics_snapshots")
                self.assertEqual(snapshot["log_id"], 1)

                db.execute("DELETE FROM users WHERE user_id = 1")
                self.assertEqual(db.query("SELECT * FROM body_logs"), [])

                db.execute(
                    "INSERT INTO users (username, email, password_hash, height_cm, sex, "
                    "birthdate, created_at) VALUES ('demo2', 'demo2@example.com', 'x', "
                    "176, 1, '2001-08-22', ?)",
                    (now,),
                )
                new_user = db.query_one("SELECT user_id FROM users WHERE username = 'demo2'")
                new_log = BodyLogDAO(db).create(
                    user_id=new_user["user_id"],
                    date=date(2026, 2, 1),
                    weight_kg=80.0,
                    intake_kcal=2000,
                    intake_is_real=True,
                    steps=5000,
                )
                self.assertGreaterEqual(new_log.log_id, 3)
            finally:
                db.close()
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_body_logs_catchup_is_a_no_op_on_an_already_current_schema(self):
        """A fresh DB (or one that already ran m0002) has no waist_cm/
        neck_cm columns to begin with -- the migration must detect that and
        do nothing, rather than erroring on a missing column."""
        conn = sqlite3.connect(":memory:")
        try:
            conn.executescript(DBModule.SCHEMA)
            from server.src.data.db.migrations import m0002_body_measurements_catchup

            m0002_body_measurements_catchup.upgrade(conn)  # must not raise
            columns = {row[1] for row in conn.execute("PRAGMA table_info(body_logs)")}
            self.assertNotIn("waist_cm", columns)
        finally:
            conn.close()

    def test_failed_migration_batch_rolls_back_atomically(self):
        """If any migration in the pending batch raises, none of the
        batch's changes (including an earlier migration's own DDL) may
        survive, and user_version must not advance -- otherwise a half-
        migrated file would look "done" on the next boot and never retry."""

        def _bad_upgrade(conn):
            conn.execute("CREATE TABLE should_not_survive (x INTEGER)")
            raise RuntimeError("boom")

        fake_migrations = [
            Migration(version=1, upgrade=lambda conn: None, name="m1"),
            Migration(version=2, upgrade=_bad_upgrade, name="bad"),
        ]

        db = DB.__new__(DB)
        db.path = ":memory:"
        db._lock = threading.Lock()
        db._conn = sqlite3.connect(":memory:")
        db._conn.row_factory = sqlite3.Row
        try:
            with patch.object(DBModule, "MIGRATIONS", fake_migrations):
                with self.assertRaises(RuntimeError):
                    db._apply_migrations()

            tables = {
                row[0]
                for row in db._conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            self.assertNotIn("should_not_survive", tables)
            self.assertEqual(db._conn.execute("PRAGMA user_version").fetchone()[0], 0)
        finally:
            db._conn.close()


class DBConcurrencyTest(unittest.TestCase):
    """Reproduces the concurrency hazard `DB._lock` guards against:
    ``check_same_thread=False`` disables Python's same-thread check but
    does not make one shared connection safe for concurrent access."""

    def test_concurrent_writes_do_not_raise(self):
        db = DB(":memory:")
        dao = UserDAO(db)
        errors = []

        def worker(thread_id: int) -> None:
            for i in range(200):
                try:
                    dao.create(
                        username=f"user_{thread_id}_{i}",
                        email=f"user_{thread_id}_{i}@example.com",
                        password_hash="hash",
                        height_cm=176,
                        sex=1,
                        birthdate=date(2001, 8, 22),
                    )
                except Exception as exc:  # pragma: no cover - failure path
                    errors.append(exc)

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(errors, [])
        row = db.query_one("SELECT COUNT(*) AS count FROM users")
        self.assertEqual(row["count"], 8 * 200)
        db.close()


if __name__ == "__main__":
    unittest.main()
