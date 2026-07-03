"""Persisted user profile — the static inputs the composition engine needs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass
class UserProfile:
    user_id: int
    username: str
    email: str
    password_hash: str
    height_cm: float
    sex: int  # 1 = male, 0 = female
    birthdate: date
    units: str
    created_at: datetime

    @staticmethod
    def from_row(row) -> "UserProfile":
        return UserProfile(
            user_id=row["user_id"],
            username=row["username"],
            email=row["email"],
            password_hash=row["password_hash"],
            height_cm=row["height_cm"],
            sex=row["sex"],
            birthdate=date.fromisoformat(row["birthdate"]),
            units=row["units"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )
