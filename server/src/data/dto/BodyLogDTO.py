from __future__ import annotations

from dataclasses import dataclass

from server.src.data.domain.BodyLog import BodyLog


@dataclass(frozen=True)
class BodyLogDTO:
    log_id: int
    user_id: int
    date: str
    weight_kg: float
    waist_cm: float
    neck_cm: float
    intake_kcal: float
    intake_is_real: bool
    steps: float
    source: str

    @staticmethod
    def from_domain(log: BodyLog) -> "BodyLogDTO":
        return BodyLogDTO(
            log_id=log.log_id,
            user_id=log.user_id,
            date=log.date.isoformat(),
            weight_kg=log.weight_kg,
            waist_cm=log.waist_cm,
            neck_cm=log.neck_cm,
            intake_kcal=log.intake_kcal,
            intake_is_real=log.intake_is_real,
            steps=log.steps,
            source=log.source,
        )
