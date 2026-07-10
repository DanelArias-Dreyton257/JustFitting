"""Sporadic body-measurement CRUD (Phase 9.1, see README): waist/neck (plus,
since Phase 9.3, nine more record-only perimeters) logged independently of
body_logs' weight/nutrition/steps cadence, resolved into the engine via
`get_effective`'s "static until next update" rule.
"""

from __future__ import annotations

from datetime import date
from typing import List, Optional

from server.src.data.db.AuditLogDAO import AuditLogDAO
from server.src.data.db.BodyMeasurementDAO import EXTENDED_FIELDS, BodyMeasurementDAO
from server.src.data.domain.BodyMeasurement import BodyMeasurement

#: All fields a caller may set, beyond user_id/date -- shared by create/
#: update/upsert and the API layer so every entry point stays in sync with
#: the schema.
MEASUREMENT_FIELDS = ("waist_cm", "neck_cm") + EXTENDED_FIELDS


class BodyMeasurementManagerError(Exception):
    """Raised for invalid body-measurement values."""


def _validate_fields(fields: dict) -> None:
    for name in MEASUREMENT_FIELDS:
        value = fields.get(name)
        if value is not None and value <= 0:
            raise BodyMeasurementManagerError(f"{name} must be positive, got {value!r}")
    waist_cm = fields.get("waist_cm")
    neck_cm = fields.get("neck_cm")
    if waist_cm is not None and neck_cm is not None and waist_cm <= neck_cm:
        raise BodyMeasurementManagerError("waist_cm must be greater than neck_cm")


class BodyMeasurementManager:
    def __init__(
        self,
        measurement_dao: BodyMeasurementDAO,
        audit_log_dao: Optional[AuditLogDAO] = None,
        metrics_cache=None,
    ):
        self.measurement_dao = measurement_dao
        self.audit_log_dao = audit_log_dao
        self.metrics_cache = metrics_cache

    def create(self, user_id: int, measurement_date: date, **fields) -> BodyMeasurement:
        _validate_fields(fields)
        measurement = self.measurement_dao.create(
            user_id=user_id, date=measurement_date, **fields
        )
        self._invalidate(user_id)
        return measurement

    def list_for_user(self, user_id: int) -> List[BodyMeasurement]:
        return self.measurement_dao.list_for_user(user_id)

    def get_by_id(self, measurement_id: int) -> Optional[BodyMeasurement]:
        return self.measurement_dao.get_by_id(measurement_id)

    def get_by_date(self, user_id: int, measurement_date: date) -> Optional[BodyMeasurement]:
        return self.measurement_dao.get_by_user_and_date(user_id, measurement_date)

    def get_effective(self, user_id: int, target_date: date) -> Optional[BodyMeasurement]:
        return self.measurement_dao.get_effective(user_id, target_date)

    def upsert_for_date(self, user_id: int, measurement_date: date, fields: dict) -> BodyMeasurement:
        """Creates a new row for `measurement_date` or merges into the
        existing one -- the Body view's date-picker-plus-save-button flow can
        re-save the same day without tripping `UNIQUE(user_id, date)`."""
        existing = self.get_by_date(user_id, measurement_date)
        if existing is None:
            return self.create(user_id, measurement_date, **fields)
        return self.update(existing.measurement_id, **fields)

    def update(self, measurement_id: int, **fields) -> Optional[BodyMeasurement]:
        existing = self.measurement_dao.get_by_id(measurement_id)
        if existing is None:
            return None
        merged = {name: fields.get(name, getattr(existing, name)) for name in MEASUREMENT_FIELDS}
        _validate_fields(merged)

        if self.audit_log_dao is not None:
            for field in MEASUREMENT_FIELDS:
                if field not in fields:
                    continue
                previous_value = getattr(existing, field)
                new_value = fields[field]
                if previous_value != new_value:
                    self.audit_log_dao.record(
                        user_id=existing.user_id,
                        entity_type="body_measurement",
                        entity_id=measurement_id,
                        field=field,
                        previous_value=str(previous_value),
                        new_value=str(new_value),
                    )

        updated = self.measurement_dao.update(measurement_id, **fields)
        self._invalidate(existing.user_id)
        return updated

    def delete(self, measurement_id: int) -> None:
        existing = self.measurement_dao.get_by_id(measurement_id)
        self.measurement_dao.delete(measurement_id)
        if existing is not None:
            self._invalidate(existing.user_id)

    def _invalidate(self, user_id: int) -> None:
        # A new/edited/deleted measurement can silently change the resolved
        # waist/neck input for every week between its date and the next
        # measurement's -- none of which necessarily touch body_logs at all
        # -- so this always invalidates the whole user's cache, the same
        # blunt-but-safe pattern engine-settings changes already use.
        if self.metrics_cache is not None:
            self.metrics_cache.invalidate_for_user(user_id)
