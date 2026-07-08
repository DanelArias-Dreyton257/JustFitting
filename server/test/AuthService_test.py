import unittest
from datetime import date, timedelta

from server.src.data.db.DB import DB
from server.src.data.db.SessionDAO import SessionDAO
from server.src.data.db.UserDAO import UserDAO
from server.src.services.AuthService import AuthService


class AuthServiceTest(unittest.TestCase):
    def setUp(self):
        self.db = DB(":memory:")
        self.auth = AuthService(SessionDAO(self.db))
        self.user_dao = UserDAO(self.db)
        self.user_id = self._create_user("demo_cut").user_id
        self.other_user_id = self._create_user("other").user_id

    def tearDown(self):
        self.db.close()

    def _create_user(self, username: str):
        return self.user_dao.create(
            username=username,
            email=f"{username}@example.com",
            password_hash="hash",
            height_cm=176,
            sex=1,
            birthdate=date(2001, 8, 22),
        )

    def test_issue_and_resolve_token(self):
        token = self.auth.issue_token(self.user_id)
        self.assertEqual(self.auth.resolve_token(token), self.user_id)

    def test_resolve_unknown_token_returns_none(self):
        self.assertIsNone(self.auth.resolve_token("does-not-exist"))

    def test_expired_token_is_rejected_and_purged(self):
        expired_auth = AuthService(SessionDAO(self.db), ttl=timedelta(seconds=-1))
        token = expired_auth.issue_token(self.user_id)
        self.assertIsNone(expired_auth.resolve_token(token))
        # Purged, so a fresh lookup with a positive TTL still fails.
        self.assertIsNone(self.auth.resolve_token(token))

    def test_resolve_token_slides_expiry_forward(self):
        short_auth = AuthService(SessionDAO(self.db), ttl=timedelta(minutes=5))
        token = short_auth.issue_token(self.user_id)
        row_before = short_auth.session_dao.get(token)
        short_auth.resolve_token(token)
        row_after = short_auth.session_dao.get(token)
        self.assertGreaterEqual(row_after["expires_at"], row_before["expires_at"])

    def test_revoke_token(self):
        token = self.auth.issue_token(self.user_id)
        self.auth.revoke_token(token)
        self.assertIsNone(self.auth.resolve_token(token))

    def test_revoke_all_for_user(self):
        token_a = self.auth.issue_token(self.user_id)
        token_b = self.auth.issue_token(self.user_id)
        self.auth.revoke_all_for_user(self.user_id)
        self.assertIsNone(self.auth.resolve_token(token_a))
        self.assertIsNone(self.auth.resolve_token(token_b))

    def test_cleanup_expired(self):
        expired_auth = AuthService(SessionDAO(self.db), ttl=timedelta(seconds=-1))
        expired_auth.issue_token(self.user_id)
        active_token = self.auth.issue_token(self.other_user_id)
        self.auth.cleanup_expired()
        self.assertIsNotNone(self.auth.resolve_token(active_token))


if __name__ == "__main__":
    unittest.main()
