from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from server.src.data.domain.BodyMeasurement import BodyMeasurement


@dataclass(frozen=True)
class BodyMeasurementDTO:
    measurement_id: int
    user_id: int
    date: str
    waist_cm: Optional[float]
    neck_cm: Optional[float]
    shoulder_cm: Optional[float]
    chest_cm: Optional[float]
    hips_cm: Optional[float]
    biceps_r_cm: Optional[float]
    biceps_l_cm: Optional[float]
    thigh_r_cm: Optional[float]
    thigh_l_cm: Optional[float]
    calf_r_cm: Optional[float]
    calf_l_cm: Optional[float]

    @staticmethod
    def from_domain(measurement: BodyMeasurement) -> "BodyMeasurementDTO":
        return BodyMeasurementDTO(
            measurement_id=measurement.measurement_id,
            user_id=measurement.user_id,
            date=measurement.date.isoformat(),
            waist_cm=measurement.waist_cm,
            neck_cm=measurement.neck_cm,
            shoulder_cm=measurement.shoulder_cm,
            chest_cm=measurement.chest_cm,
            hips_cm=measurement.hips_cm,
            biceps_r_cm=measurement.biceps_r_cm,
            biceps_l_cm=measurement.biceps_l_cm,
            thigh_r_cm=measurement.thigh_r_cm,
            thigh_l_cm=measurement.thigh_l_cm,
            calf_r_cm=measurement.calf_r_cm,
            calf_l_cm=measurement.calf_l_cm,
        )
