from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from server.src.data.db.DB import DB


class SessionDAO:
    def __init__(self, db: DB):
        self.db = db

    def create(self, token: str, user_id: int, expires_at: datetime) -> None:
        created_at = datetime.now(timezone.utc).isoformat()
        self.db.execute(
            "INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (token, user_id, created_at, expires_at.isoformat()),
        )

    def get(self, token: str) -> Optional[object]:
        return self.db.query_one("SELECT * FROM sessions WHERE token = ?", (token,))

    def update_expiry(self, token: str, expires_at: datetime) -> None:
        self.db.execute(
            "UPDATE sessions SET expires_at = ? WHERE token = ?",
            (expires_at.isoformat(), token),
        )

    def delete(self, token: str) -> None:
        self.db.execute("DELETE FROM sessions WHERE token = ?", (token,))

    def delete_expired(self, as_of: datetime) -> None:
        self.db.execute(
            "DELETE FROM sessions WHERE expires_at < ?", (as_of.isoformat(),)
        )

    def delete_all_for_user(self, user_id: int) -> None:
        self.db.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
