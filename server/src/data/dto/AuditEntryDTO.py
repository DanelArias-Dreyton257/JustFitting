from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from server.src.data.domain.AuditEntry import AuditEntry


@dataclass(frozen=True)
class AuditEntryDTO:
    audit_id: int
    user_id: int
    entity_type: str
    entity_id: int
    field: str
    previous_value: Optional[str]
    new_value: Optional[str]
    changed_at: str
    engine_version: Optional[int]

    @staticmethod
    def from_domain(entry: AuditEntry) -> "AuditEntryDTO":
        return AuditEntryDTO(
            audit_id=entry.audit_id,
            user_id=entry.user_id,
            entity_type=entry.entity_type,
            entity_id=entry.entity_id,
            field=entry.field,
            previous_value=entry.previous_value,
            new_value=entry.new_value,
            changed_at=entry.changed_at.isoformat(),
            engine_version=entry.engine_version,
        )
