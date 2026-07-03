import unittest
from datetime import date, datetime, timedelta, timezone

from server.src.data.db.AuditLogDAO import AuditLogDAO
from server.src.data.db.DB import DB
from server.src.data.db.SessionDAO import SessionDAO
from server.src.data.db.UserDAO import UserDAO
from server.src.services.PasswordResetService import PasswordResetService
from server.src.services.UserManager import verify_password


class PasswordResetServiceTest(unittest.TestCase):
    def setUp(self):
        self.db = DB(":memory:")
        self.user_dao = UserDAO(self.db)
        self.session_dao = SessionDAO(self.db)
        self.audit_log_dao = AuditLogDAO(self.db)
        self.service = PasswordResetService(
            self.user_dao, self.session_dao, audit_log_dao=self.audit_log_dao
        )
        self.user = self.user_dao.create(
            username="danel",
            email="danel@example.com",
            password_hash="old-hash",
            height_cm=176,
            sex=1,
            birthdate=date(2001, 8, 22),
        )

    def tearDown(self):
        self.db.close()

    def test_reset_password_unknown_identifier_returns_false(self):
        self.assertFalse(self.service.reset_password("nobody-here", "whatever12"))

    def test_reset_password_by_username_updates_the_password(self):
        ok = self.service.reset_password("danel", "brand-new-password")
        self.assertTrue(ok)
        updated = self.user_dao.get_by_id(self.user.user_id)
        self.assertTrue(verify_password("brand-new-password", updated.password_hash))

    def test_reset_password_by_email_also_works(self):
        ok = self.service.reset_password("danel@example.com", "brand-new-password")
        self.assertTrue(ok)

    def test_reset_password_revokes_existing_sessions(self):
        self.session_dao.create(
            "some-token", self.user.user_id, datetime.now(timezone.utc) + timedelta(days=1)
        )
        self.service.reset_password("danel", "brand-new-password")
        self.assertIsNone(self.session_dao.get("some-token"))

    def test_reset_password_is_audited_without_leaking_the_password(self):
        self.service.reset_password("danel", "brand-new-password")
        entries = self.audit_log_dao.list_for_user(self.user.user_id)
        password_entries = [e for e in entries if e.field == "password"]
        self.assertEqual(len(password_entries), 1)
        self.assertNotIn("brand-new-password", password_entries[0].new_value)


if __name__ == "__main__":
    unittest.main()
