import unittest
from datetime import date

from server.src.data.db.DB import DB
from server.src.data.db.UserDAO import UserDAO
from server.src.services.UserManager import (
    UserManager,
    UserManagerError,
    hash_password,
    verify_password,
)


class UserManagerTest(unittest.TestCase):
    def setUp(self):
        self.db = DB(":memory:")
        self.manager = UserManager(UserDAO(self.db))

    def tearDown(self):
        self.db.close()

    def _register(self, **overrides):
        defaults = dict(
            username="danel",
            email="danel@example.com",
            password="correct horse battery staple",
            height_cm=176,
            sex=1,
            birthdate=date(2001, 8, 22),
            target_bf=0.15,
            weekly_rate=-0.005,
        )
        defaults.update(overrides)
        return self.manager.register(**defaults)

    def test_password_hash_roundtrip(self):
        hashed = hash_password("s3cret")
        self.assertTrue(verify_password("s3cret", hashed))
        self.assertFalse(verify_password("wrong", hashed))

    def test_password_hash_uses_random_salt(self):
        self.assertNotEqual(hash_password("s3cret"), hash_password("s3cret"))

    def test_register_and_authenticate(self):
        profile = self._register()
        self.assertEqual(profile.username, "danel")

        authenticated = self.manager.authenticate(
            "danel", "correct horse battery staple"
        )
        self.assertEqual(authenticated.user_id, profile.user_id)

        by_email = self.manager.authenticate(
            "danel@example.com", "correct horse battery staple"
        )
        self.assertEqual(by_email.user_id, profile.user_id)

        self.assertIsNone(self.manager.authenticate("danel", "wrong password"))

    def test_register_rejects_duplicate_username_or_email(self):
        self._register()
        with self.assertRaises(UserManagerError):
            self._register(email="other@example.com")
        with self.assertRaises(UserManagerError):
            self._register(username="other")

    def test_register_validates_profile_fields(self):
        with self.assertRaises(UserManagerError):
            self._register(height_cm=0)
        with self.assertRaises(UserManagerError):
            self._register(sex=2)
        with self.assertRaises(UserManagerError):
            self._register(target_bf=1.5)

    def test_update_profile_ignores_protected_fields(self):
        profile = self._register()
        updated = self.manager.update_profile(
            profile.user_id, height_cm=180, username="hacker", password_hash="bypass"
        )
        self.assertEqual(updated.height_cm, 180)
        self.assertEqual(updated.username, "danel")
        self.assertTrue(
            verify_password("correct horse battery staple", updated.password_hash)
        )

    def test_change_password(self):
        profile = self._register()
        self.manager.change_password(
            profile.user_id, "correct horse battery staple", "new password"
        )
        self.assertIsNotNone(self.manager.authenticate("danel", "new password"))
        self.assertIsNone(
            self.manager.authenticate("danel", "correct horse battery staple")
        )

    def test_change_password_rejects_wrong_current_password(self):
        profile = self._register()
        with self.assertRaises(UserManagerError):
            self.manager.change_password(profile.user_id, "wrong", "new password")

    def test_delete_user(self):
        profile = self._register()
        self.manager.delete_user(profile.user_id)
        self.assertIsNone(self.manager.get_profile(profile.user_id))


if __name__ == "__main__":
    unittest.main()
