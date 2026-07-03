"""Direct password reset, independent of the existing authenticated
`UserManager.change_password` (which requires the old password and is
unaffected by this).

There is no email/token verification step -- given an existing username
or email, `reset_password` sets the new password immediately. That's a
deliberate, temporary tradeoff for a self-hosted personal project with no
mail server: see the README's "Known limitations" / "Future work" for the
plan to gate this behind an emailed, single-use token later.
"""

from __future__ import annotations

from typing import Optional

from server.src.data.db.AuditLogDAO import AuditLogDAO
from server.src.data.db.SessionDAO import SessionDAO
from server.src.data.db.UserDAO import UserDAO
from server.src.services import UserManager as user_manager_module


class PasswordResetService:
    def __init__(
        self,
        user_dao: UserDAO,
        session_dao: SessionDAO,
        audit_log_dao: Optional[AuditLogDAO] = None,
    ):
        self.user_dao = user_dao
        self.session_dao = session_dao
        self.audit_log_dao = audit_log_dao

    def reset_password(self, identifier: str, new_password: str) -> bool:
        """Looks up `identifier` as a username or email and immediately sets
        `new_password`. Returns False if no matching account exists."""
        user = self.user_dao.get_by_username(identifier) or self.user_dao.get_by_email(
            identifier
        )
        if user is None:
            return False

        self.user_dao.update(
            user.user_id, password_hash=user_manager_module.hash_password(new_password)
        )
        self.session_dao.delete_all_for_user(user.user_id)

        if self.audit_log_dao is not None:
            self.audit_log_dao.record(
                user_id=user.user_id,
                entity_type="user",
                entity_id=user.user_id,
                field="password",
                previous_value=None,
                new_value="[reset without verification]",
            )
        return True
