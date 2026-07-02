from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from server.src.data.db.DB import DB
from server.src.data.domain.UserProfile import UserProfile


class UserDAO:
    def __init__(self, db: DB):
        self.db = db

    def create(
        self,
        *,
        username: str,
        email: str,
        password_hash: str,
        height_cm: float,
        sex: int,
        birthdate: date,
        target_bf: float,
        weekly_rate: float,
        units: str = "metric",
    ) -> UserProfile:
        created_at = datetime.now(timezone.utc).isoformat()
        cursor = self.db.execute(
            """
            INSERT INTO users
                (username, email, password_hash, height_cm, sex, birthdate,
                 target_bf, weekly_rate, units, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                username,
                email,
                password_hash,
                height_cm,
                sex,
                birthdate.isoformat(),
                target_bf,
                weekly_rate,
                units,
                created_at,
            ),
        )
        return self.get_by_id(cursor.lastrowid)

    def get_by_id(self, user_id: int) -> Optional[UserProfile]:
        row = self.db.query_one("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return UserProfile.from_row(row) if row else None

    def get_by_username(self, username: str) -> Optional[UserProfile]:
        row = self.db.query_one("SELECT * FROM users WHERE username = ?", (username,))
        return UserProfile.from_row(row) if row else None

    def get_by_email(self, email: str) -> Optional[UserProfile]:
        row = self.db.query_one("SELECT * FROM users WHERE email = ?", (email,))
        return UserProfile.from_row(row) if row else None

    def update(self, user_id: int, **fields) -> Optional[UserProfile]:
        if not fields:
            return self.get_by_id(user_id)
        columns = [f"{key} = ?" for key in fields]
        params = [
            value.isoformat() if hasattr(value, "isoformat") else value
            for value in fields.values()
        ]
        params.append(user_id)
        self.db.execute(
            f"UPDATE users SET {', '.join(columns)} WHERE user_id = ?", tuple(params)
        )
        return self.get_by_id(user_id)

    def delete(self, user_id: int) -> None:
        self.db.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
