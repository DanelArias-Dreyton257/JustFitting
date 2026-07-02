"""Profile CRUD and password hashing (PBKDF2-HMAC-SHA256)."""

from __future__ import annotations

import hashlib
import hmac
import os
from datetime import date
from typing import Optional

from server.src.data.db.UserDAO import UserDAO
from server.src.data.domain.UserProfile import UserProfile

PBKDF2_ITERATIONS = 260_000
SALT_BYTES = 16


class UserManagerError(Exception):
    """Raised for user-facing profile/credential failures."""


def hash_password(password: str, salt: Optional[bytes] = None) -> str:
    if salt is None:
        salt = os.urandom(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS
    )
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        salt_hex, digest_hex = password_hash.split("$", 1)
    except ValueError:
        return False
    salt = bytes.fromhex(salt_hex)
    expected = hash_password(password, salt)
    return hmac.compare_digest(expected, password_hash)


class UserManager:
    def __init__(self, user_dao: UserDAO):
        self.user_dao = user_dao

    def register(
        self,
        *,
        username: str,
        email: str,
        password: str,
        height_cm: float,
        sex: int,
        birthdate: date,
        target_bf: float,
        weekly_rate: float,
        units: str = "metric",
    ) -> UserProfile:
        if self.user_dao.get_by_username(username):
            raise UserManagerError(f"username '{username}' is already taken")
        if self.user_dao.get_by_email(email):
            raise UserManagerError(f"email '{email}' is already registered")
        if height_cm <= 0:
            raise UserManagerError("height_cm must be positive")
        if sex not in (0, 1):
            raise UserManagerError("sex must be 0 (female) or 1 (male)")
        if not (0 < target_bf < 1):
            raise UserManagerError("target_bf must be a fraction between 0 and 1")

        return self.user_dao.create(
            username=username,
            email=email,
            password_hash=hash_password(password),
            height_cm=height_cm,
            sex=sex,
            birthdate=birthdate,
            target_bf=target_bf,
            weekly_rate=weekly_rate,
            units=units,
        )

    def authenticate(
        self, username_or_email: str, password: str
    ) -> Optional[UserProfile]:
        profile = self.user_dao.get_by_username(
            username_or_email
        ) or self.user_dao.get_by_email(username_or_email)
        if profile is None:
            return None
        if not verify_password(password, profile.password_hash):
            return None
        return profile

    def get_profile(self, user_id: int) -> Optional[UserProfile]:
        return self.user_dao.get_by_id(user_id)

    def update_profile(self, user_id: int, **fields) -> Optional[UserProfile]:
        fields.pop("password_hash", None)
        fields.pop("username", None)
        return self.user_dao.update(user_id, **fields)

    def change_password(
        self, user_id: int, old_password: str, new_password: str
    ) -> None:
        profile = self.user_dao.get_by_id(user_id)
        if profile is None:
            raise UserManagerError("user not found")
        if not verify_password(old_password, profile.password_hash):
            raise UserManagerError("current password is incorrect")
        self.user_dao.update(user_id, password_hash=hash_password(new_password))

    def delete_user(self, user_id: int) -> None:
        self.user_dao.delete(user_id)
