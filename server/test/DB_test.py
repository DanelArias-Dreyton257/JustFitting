import threading
import unittest
from datetime import date, datetime, timedelta, timezone

from server.src.data.db.BodyLogDAO import BodyLogDAO
from server.src.data.db.DB import DB
from server.src.data.db.SessionDAO import SessionDAO
from server.src.data.db.UserDAO import UserDAO


class DBTestCase(unittest.TestCase):
    def setUp(self):
        self.db = DB(":memory:")

    def tearDown(self):
        self.db.close()

    def test_migrate_is_idempotent(self):
        version_before = self.db.query_one("PRAGMA user_version")[0]
        self.db.migrate()
        version_after = self.db.query_one("PRAGMA user_version")[0]
        self.assertEqual(version_before, version_after)
        self.assertGreater(version_after, 0)

    def test_user_dao_crud(self):
        dao = UserDAO(self.db)
        profile = dao.create(
            username="danel",
            email="danel@example.com",
            password_hash="hash",
            height_cm=176,
            sex=1,
            birthdate=date(2001, 8, 22),
            target_bf=0.15,
            weekly_rate=-0.005,
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
            target_bf=0.15,
            weekly_rate=-0.005,
        )
        with self.assertRaises(Exception):
            dao.create(
                username="danel",
                email="other@example.com",
                password_hash="hash",
                height_cm=176,
                sex=1,
                birthdate=date(2001, 8, 22),
                target_bf=0.15,
                weekly_rate=-0.005,
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
            target_bf=0.15,
            weekly_rate=-0.005,
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
            target_bf=0.15,
            weekly_rate=-0.005,
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
            target_bf=0.15,
            weekly_rate=-0.005,
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
            target_bf=0.15,
            weekly_rate=-0.005,
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
                        target_bf=0.15,
                        weekly_rate=-0.005,
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
