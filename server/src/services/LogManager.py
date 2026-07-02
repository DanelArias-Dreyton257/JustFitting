"""Weekly body-log CRUD, plus the verified "Danel" reference series used by
scripts/seed_demo_data.sh and the JUSTFITTING_SEED_DEMO boot seeder.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import List, Optional

from server.src.data.db.BodyLogDAO import BodyLogDAO
from server.src.data.domain.BodyLog import BodyLog
from server.src.services.composition.CompositionEngine import validate_log_input
from server.src.services.composition.models import LogInput, ProfileParams


@dataclass(frozen=True)
class DemoProfile:
    height_cm: float
    sex: int
    birthdate: date
    target_bf: float
    weekly_rate: float


#: The verified reference profile and its two documented boundary logs
#: (docs/composition_spec.md). Weeks in between are linearly interpolated
#: so the demo dataset is a plausible, continuous weekly series.
DEMO_PROFILE = DemoProfile(
    height_cm=176,
    sex=1,
    birthdate=date(2001, 8, 22),
    target_bf=0.15,
    weekly_rate=-0.005,
)
DEMO_FIRST_LOG = {
    "date": date(2025, 12, 28),
    "weight_kg": 97.0,
    "waist_cm": 91.0,
    "neck_cm": 38.5,
}
DEMO_LAST_LOG = {
    "date": date(2026, 6, 26),
    "weight_kg": 90.7,
    "waist_cm": 80.0,
    "neck_cm": 35.0,
}
DEMO_STEPS_START = 6000
DEMO_STEPS_END = 5000
DEMO_INTAKE_START = 2400.0
DEMO_INTAKE_END = 2014.30


def _interpolate(start: float, end: float, fraction: float) -> float:
    return start + (end - start) * fraction


class LogManager:
    def __init__(self, log_dao: BodyLogDAO):
        self.log_dao = log_dao

    def create_log(
        self,
        *,
        user_id: int,
        log_date: date,
        weight_kg: float,
        waist_cm: float,
        neck_cm: float,
        intake_kcal: float,
        steps: float,
        intake_is_real: bool = True,
        source: str = "real",
    ) -> BodyLog:
        candidate = LogInput(
            date=log_date,
            weight_kg=weight_kg,
            waist_cm=waist_cm,
            neck_cm=neck_cm,
            intake_kcal=intake_kcal,
            steps=steps,
            intake_is_real=intake_is_real,
        )
        validate_log_input(candidate)
        return self.log_dao.create(
            user_id=user_id,
            date=log_date,
            weight_kg=weight_kg,
            waist_cm=waist_cm,
            neck_cm=neck_cm,
            intake_kcal=intake_kcal,
            intake_is_real=intake_is_real,
            steps=steps,
            source=source,
        )

    def list_logs(self, user_id: int) -> List[BodyLog]:
        return self.log_dao.list_for_user(user_id)

    def get_log(self, log_id: int) -> Optional[BodyLog]:
        return self.log_dao.get_by_id(log_id)

    def update_log(self, log_id: int, **fields) -> Optional[BodyLog]:
        existing = self.log_dao.get_by_id(log_id)
        if existing is None:
            return None
        merged = LogInput(
            date=fields.get("date", existing.date),
            weight_kg=fields.get("weight_kg", existing.weight_kg),
            waist_cm=fields.get("waist_cm", existing.waist_cm),
            neck_cm=fields.get("neck_cm", existing.neck_cm),
            intake_kcal=fields.get("intake_kcal", existing.intake_kcal),
            steps=fields.get("steps", existing.steps),
            intake_is_real=fields.get("intake_is_real", existing.intake_is_real),
        )
        validate_log_input(merged)
        return self.log_dao.update(log_id, **fields)

    def delete_log(self, log_id: int) -> None:
        self.log_dao.delete(log_id)

    def to_engine_inputs(self, logs: List[BodyLog]) -> List[LogInput]:
        return [
            LogInput(
                date=log.date,
                weight_kg=log.weight_kg,
                waist_cm=log.waist_cm,
                neck_cm=log.neck_cm,
                intake_kcal=log.intake_kcal,
                steps=log.steps,
                intake_is_real=log.intake_is_real,
            )
            for log in sorted(logs, key=lambda log: log.date)
        ]

    def compute_adherence(self, logs: List[BodyLog], results) -> Optional[float]:
        """Mean IntakeDiff over real-intake rows only (see docs/composition_spec.md)."""
        real_diffs = [
            result.intake_diff
            for log, result in zip(logs, results)
            if log.intake_is_real
        ]
        if not real_diffs:
            return None
        return sum(real_diffs) / len(real_diffs)

    def seed_reference_series(self, user_id: int) -> List[BodyLog]:
        """Seed the weekly Danel reference series between the two documented
        boundary logs (idempotent: no-op if the user already has logs)."""
        if self.log_dao.list_for_user(user_id):
            return []

        start = DEMO_FIRST_LOG["date"]
        end = DEMO_LAST_LOG["date"]
        total_weeks = (end - start).days // 7

        created: List[BodyLog] = []
        for week in range(total_weeks + 1):
            log_date = start + timedelta(days=7 * week)
            fraction = week / total_weeks
            weight_kg = _interpolate(
                DEMO_FIRST_LOG["weight_kg"], DEMO_LAST_LOG["weight_kg"], fraction
            )
            waist_cm = _interpolate(
                DEMO_FIRST_LOG["waist_cm"], DEMO_LAST_LOG["waist_cm"], fraction
            )
            neck_cm = _interpolate(
                DEMO_FIRST_LOG["neck_cm"], DEMO_LAST_LOG["neck_cm"], fraction
            )
            steps = _interpolate(DEMO_STEPS_START, DEMO_STEPS_END, fraction)
            intake_kcal = _interpolate(DEMO_INTAKE_START, DEMO_INTAKE_END, fraction)

            # The two documented boundary rows are reproduced exactly.
            if week == 0:
                weight_kg, waist_cm, neck_cm = (
                    DEMO_FIRST_LOG["weight_kg"],
                    DEMO_FIRST_LOG["waist_cm"],
                    DEMO_FIRST_LOG["neck_cm"],
                )
            elif week == total_weeks:
                weight_kg, waist_cm, neck_cm = (
                    DEMO_LAST_LOG["weight_kg"],
                    DEMO_LAST_LOG["waist_cm"],
                    DEMO_LAST_LOG["neck_cm"],
                )

            created.append(
                self.create_log(
                    user_id=user_id,
                    log_date=log_date,
                    weight_kg=round(weight_kg, 1),
                    waist_cm=round(waist_cm, 1),
                    neck_cm=round(neck_cm, 1),
                    intake_kcal=round(intake_kcal, 2),
                    steps=round(steps),
                    intake_is_real=True,
                    source="real",
                )
            )
        return created


def demo_profile_params() -> ProfileParams:
    return ProfileParams(
        height_cm=DEMO_PROFILE.height_cm,
        sex=DEMO_PROFILE.sex,
        birthdate=DEMO_PROFILE.birthdate,
        target_bf=DEMO_PROFILE.target_bf,
        weekly_rate=DEMO_PROFILE.weekly_rate,
    )
