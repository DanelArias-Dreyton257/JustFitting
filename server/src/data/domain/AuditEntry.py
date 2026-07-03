"""One field-level change record: who/what/when/before/after.

Written for every profile, goal-plan, and body-log edit so historical
values stay reproducible even after the record itself is changed again.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class AuditEntry:
    audit_id: int
    user_id: int
    entity_type: str  # "profile" | "goal_plan" | "body_log"
    entity_id: int
    field: str
    previous_value: Optional[str]
    new_value: Optional[str]
    changed_at: datetime
    engine_version: Optional[int]

    @staticmethod
    def from_row(row) -> "AuditEntry":
        return AuditEntry(
            audit_id=row["audit_id"],
            user_id=row["user_id"],
            entity_type=row["entity_type"],
            entity_id=row["entity_id"],
            field=row["field"],
            previous_value=row["previous_value"],
            new_value=row["new_value"],
            changed_at=datetime.fromisoformat(row["changed_at"]),
            engine_version=row["engine_version"],
        )
