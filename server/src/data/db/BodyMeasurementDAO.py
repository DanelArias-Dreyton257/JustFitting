from __future__ import annotations

from datetime import date, datetime, timezone
from typing import List, Optional

from server.src.data.db.DB import DB
from server.src.data.domain.BodyMeasurement import BodyMeasurement

#: The nine Phase 9.3 record-only columns, alongside waist_cm/neck_cm --
#: shared by create/update so both stay in sync with the schema.
EXTENDED_FIELDS = (
    "shoulder_cm",
    "chest_cm",
    "hips_cm",
    "biceps_r_cm",
    "biceps_l_cm",
    "thigh_r_cm",
    "thigh_l_cm",
    "calf_r_cm",
    "calf_l_cm",
)


class BodyMeasurementDAO:
    def __init__(self, db: DB):
        self.db = db

    def create(
        self,
        *,
        user_id: int,
        date: date,
        waist_cm: Optional[float] = None,
        neck_cm: Optional[float] = None,
        shoulder_cm: Optional[float] = None,
        chest_cm: Optional[float] = None,
        hips_cm: Optional[float] = None,
        biceps_r_cm: Optional[float] = None,
        biceps_l_cm: Optional[float] = None,
        thigh_r_cm: Optional[float] = None,
        thigh_l_cm: Optional[float] = None,
        calf_r_cm: Optional[float] = None,
        calf_l_cm: Optional[float] = None,
    ) -> BodyMeasurement:
        created_at = datetime.now(timezone.utc).isoformat()
        cursor = self.db.execute(
            """
            INSERT INTO body_measurements
                (user_id, date, waist_cm, neck_cm, shoulder_cm, chest_cm, hips_cm,
                 biceps_r_cm, biceps_l_cm, thigh_r_cm, thigh_l_cm, calf_r_cm,
                 calf_l_cm, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                date.isoformat(),
                waist_cm,
                neck_cm,
                shoulder_cm,
                chest_cm,
                hips_cm,
                biceps_r_cm,
                biceps_l_cm,
                thigh_r_cm,
                thigh_l_cm,
                calf_r_cm,
                calf_l_cm,
                created_at,
            ),
        )
        return self.get_by_id(cursor.lastrowid)

    def get_by_id(self, measurement_id: int) -> Optional[BodyMeasurement]:
        row = self.db.query_one(
            "SELECT * FROM body_measurements WHERE measurement_id = ?", (measurement_id,)
        )
        return BodyMeasurement.from_row(row) if row else None

    def list_for_user(self, user_id: int) -> List[BodyMeasurement]:
        rows = self.db.query(
            "SELECT * FROM body_measurements WHERE user_id = ? ORDER BY date ASC", (user_id,)
        )
        return [BodyMeasurement.from_row(row) for row in rows]

    def get_by_user_and_date(self, user_id: int, target_date: date) -> Optional[BodyMeasurement]:
        row = self.db.query_one(
            "SELECT * FROM body_measurements WHERE user_id = ? AND date = ?",
            (user_id, target_date.isoformat()),
        )
        return BodyMeasurement.from_row(row) if row else None

    def get_effective(self, user_id: int, target_date: date) -> Optional[BodyMeasurement]:
        """The most recent measurement with `date <= target_date` -- "static
        until next update" (Phase 9.1, see README). `None` if the account has
        never logged a measurement on or before that date."""
        row = self.db.query_one(
            """
            SELECT * FROM body_measurements
            WHERE user_id = ? AND date <= ?
            ORDER BY date DESC, measurement_id DESC
            LIMIT 1
            """,
            (user_id, target_date.isoformat()),
        )
        return BodyMeasurement.from_row(row) if row else None

    def update(self, measurement_id: int, **fields) -> Optional[BodyMeasurement]:
        if not fields:
            return self.get_by_id(measurement_id)
        columns = [f"{key} = ?" for key in fields]
        params = []
        for key, value in fields.items():
            if hasattr(value, "isoformat"):
                value = value.isoformat()
            params.append(value)
        params.append(measurement_id)
        self.db.execute(
            f"UPDATE body_measurements SET {', '.join(columns)} WHERE measurement_id = ?",
            tuple(params),
        )
        return self.get_by_id(measurement_id)

    def delete(self, measurement_id: int) -> None:
        self.db.execute("DELETE FROM body_measurements WHERE measurement_id = ?", (measurement_id,))

    def delete_all_for_user(self, user_id: int) -> None:
        self.db.execute("DELETE FROM body_measurements WHERE user_id = ?", (user_id,))
