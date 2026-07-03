from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from server.src.data.db.DB import DB
from server.src.data.domain.AuditEntry import AuditEntry


class AuditLogDAO:
    def __init__(self, db: DB):
        self.db = db

    def record(
        self,
        *,
        user_id: int,
        entity_type: str,
        entity_id: int,
        field: str,
        previous_value: Optional[str],
        new_value: Optional[str],
        engine_version: Optional[int] = None,
    ) -> AuditEntry:
        changed_at = datetime.now(timezone.utc).isoformat()
        cursor = self.db.execute(
            """
            INSERT INTO audit_log
                (user_id, entity_type, entity_id, field, previous_value,
                 new_value, changed_at, engine_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                entity_type,
                entity_id,
                field,
                previous_value,
                new_value,
                changed_at,
                engine_version,
            ),
        )
        return self.get_by_id(cursor.lastrowid)

    def get_by_id(self, audit_id: int) -> Optional[AuditEntry]:
        row = self.db.query_one("SELECT * FROM audit_log WHERE audit_id = ?", (audit_id,))
        return AuditEntry.from_row(row) if row else None

    def list_for_user(self, user_id: int) -> List[AuditEntry]:
        rows = self.db.query(
            """
            SELECT * FROM audit_log
            WHERE user_id = ?
            ORDER BY changed_at DESC, audit_id DESC
            """,
            (user_id,),
        )
        return [AuditEntry.from_row(row) for row in rows]
