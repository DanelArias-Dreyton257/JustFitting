import threading
import unittest
from datetime import date, datetime, timedelta, timezone

from server.src.data.db import DB as DBModule
from server.src.data.db.BodyLogDAO import BodyLogDAO
from server.src.data.db.DB import DB
from server.src.data.db.GoalPlanDAO import GoalPlanDAO
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
            username="danel",
            email="danel@example.com",
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
            username="danel",
            email="danel@example.com",
            password_hash="hash",
            height_cm=176,
            sex=1,
            birthdate=date(2001, 8, 22),
        )
        self.assertIsNotNone(profile.user_id)

        by_username = dao.get_by_username("danel")
        self.assertEqual(by_username.user_id, profile.user_id)

        by_email = dao.get_by_email("danel@example.com")
        self.assertEqual(by_email.user_id, profile.user_id)

        updated = dao.update(profile.user_id, height_cm=177)
        self.assertEqual(updated.height_cm, 177)

        dao.delete(profile.user_id)
        self.assertIsNone(dao.get_by_id(profile.user_id))

    def test_user_unique_constraints(self):
        dao = UserDAO(self.db)
        dao.create(
            username="danel",
            email="danel@example.com",
            password_hash="hash",
            height_cm=176,
            sex=1,
            birthdate=date(2001, 8, 22),
        )
        with self.assertRaises(Exception):
            dao.create(
                username="danel",
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
            username="danel",
            email="danel@example.com",
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
            username="danel",
            email="danel@example.com",
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
            username="danel",
            email="danel@example.com",
            password_hash="hash",
            height_cm=176,
            sex=1,
            birthdate=date(2001, 8, 22),
        )
        log = log_dao.create(
            user_id=profile.user_id,
            date=date(2026, 6, 26),
            weight_kg=90.7,
            waist_cm=80.0,
            neck_cm=35.0,
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
                waist_cm=80.0,
                neck_cm=35.0,
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
            username="danel",
            email="danel@example.com",
            password_hash="hash",
            height_cm=176,
            sex=1,
            birthdate=date(2001, 8, 22),
        )
        log_dao.create(
            user_id=profile.user_id,
            date=date(2026, 6, 26),
            weight_kg=90.7,
            waist_cm=80.0,
            neck_cm=35.0,
            intake_kcal=2014.30,
            intake_is_real=True,
            steps=5000,
        )
        user_dao.delete(profile.user_id)
        self.assertEqual(log_dao.list_for_user(profile.user_id), [])

    def test_goal_plan_dao_history_and_deactivate(self):
        user_dao = UserDAO(self.db)
        goal_dao = GoalPlanDAO(self.db)
        profile = user_dao.create(
            username="danel",
            email="danel@example.com",
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
