"""Sporadically-logged body measurement (Phase 9.1, see README): perimeters
are decoupled from body_logs' weight/nutrition/steps cadence -- a value is
"static" from one measurement to the next for every computation in between
(see BodyMeasurementManager.get_effective).

waist_cm/neck_cm are the only fields CompositionEngine ever reads (via the
resolution layer); the nine Phase 9.3 fields are record-only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional


@dataclass
class BodyMeasurement:
    measurement_id: int
    user_id: int
    date: date
    waist_cm: Optional[float]
    neck_cm: Optional[float]
    created_at: datetime
    # Phase 9.3: record-only, never read by CompositionEngine.
    shoulder_cm: Optional[float] = None
    chest_cm: Optional[float] = None
    hips_cm: Optional[float] = None
    biceps_r_cm: Optional[float] = None
    biceps_l_cm: Optional[float] = None
    thigh_r_cm: Optional[float] = None
    thigh_l_cm: Optional[float] = None
    calf_r_cm: Optional[float] = None
    calf_l_cm: Optional[float] = None

    @staticmethod
    def from_row(row) -> "BodyMeasurement":
        return BodyMeasurement(
            measurement_id=row["measurement_id"],
            user_id=row["user_id"],
            date=date.fromisoformat(row["date"]),
            waist_cm=row["waist_cm"],
            neck_cm=row["neck_cm"],
            created_at=datetime.fromisoformat(row["created_at"]),
            shoulder_cm=row["shoulder_cm"],
            chest_cm=row["chest_cm"],
            hips_cm=row["hips_cm"],
            biceps_r_cm=row["biceps_r_cm"],
            biceps_l_cm=row["biceps_l_cm"],
            thigh_r_cm=row["thigh_r_cm"],
            thigh_l_cm=row["thigh_l_cm"],
            calf_r_cm=row["calf_r_cm"],
            calf_l_cm=row["calf_l_cm"],
        )
