"""Bearer-token session issuance with sliding expiry, DB-persisted."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from server.src.data.db.SessionDAO import SessionDAO

TOKEN_BYTES = 32
SESSION_TTL = timedelta(days=14)


class AuthService:
    def __init__(self, session_dao: SessionDAO, ttl: timedelta = SESSION_TTL):
        self.session_dao = session_dao
        self.ttl = ttl

    def issue_token(self, user_id: int) -> str:
        token = secrets.token_urlsafe(TOKEN_BYTES)
        expires_at = datetime.now(timezone.utc) + self.ttl
        self.session_dao.create(token, user_id, expires_at)
        return token

    def resolve_token(self, token: str) -> Optional[int]:
        """Return the user_id for a valid token, sliding its expiry forward."""
        row = self.session_dao.get(token)
        if row is None:
            return None
        expires_at = datetime.fromisoformat(row["expires_at"])
        if expires_at < datetime.now(timezone.utc):
            self.session_dao.delete(token)
            return None
        self.session_dao.update_expiry(token, datetime.now(timezone.utc) + self.ttl)
        return row["user_id"]

    def revoke_token(self, token: str) -> None:
        self.session_dao.delete(token)

    def revoke_all_for_user(self, user_id: int) -> None:
        self.session_dao.delete_all_for_user(user_id)

    def cleanup_expired(self) -> None:
        self.session_dao.delete_expired(datetime.now(timezone.utc))
