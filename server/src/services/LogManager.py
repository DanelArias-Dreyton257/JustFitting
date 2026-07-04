"""Weekly body-log CRUD, plus the verified "Danel" (cut) and "Sergio"
(bulk) reference series used by scripts/seed_demo_data.sh and the
JUSTFITTING_SEED_DEMO boot seeder (see services/DemoSeeder.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import List, Optional

from server.src.data.db.AuditLogDAO import AuditLogDAO
from server.src.data.db.BodyLogDAO import BodyLogDAO
from server.src.data.domain.BodyLog import BodyLog
from server.src.services.composition.CompositionEngine import validate_log_input
from server.src.services.composition.models import LogInput, ProfileParams

LOG_EDITABLE_FIELDS = (
    "date",
    "weight_kg",
    "waist_cm",
    "neck_cm",
    "intake_kcal",
    "intake_is_real",
    "steps",
    "cardio_kcal",
    "source",
    "granularity",
    "carbs_g",
    "fat_g",
    "protein_g",
)

GRANULARITIES = ("daily", "weekly")


def _validate_granularity(granularity: str) -> None:
    if granularity not in GRANULARITIES:
        raise ValueError(f"granularity must be one of {GRANULARITIES}, got {granularity!r}")


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

#: Sergio's bulk/volume reference profile (docs/composition_spec.md's
#: "Oleada 2" section) -- a second worked profile alongside Danel's above,
#: a lean bulk instead of a cut. The source doc only gives a single-week
#: snapshot, not a full series, so the boundary logs and trajectory below
#: are this implementation's own plausible demo data, not a documented
#: golden reference (unlike Danel's, don't pin new tests to these numbers).
SERGIO_PROFILE = DemoProfile(
    height_cm=194,
    sex=1,
    birthdate=date(2001, 4, 5),
    target_bf=0.15,
    weekly_rate=0.005,
)
SERGIO_FIRST_LOG = {
    "date": date(2026, 1, 4),
    "weight_kg": 88.0,
    "waist_cm": 84.0,
    "neck_cm": 39.0,
}
SERGIO_LAST_LOG = {
    "date": date(2026, 6, 28),
    "weight_kg": 95.5,
    "waist_cm": 84.5,
    "neck_cm": 39.0,
}
SERGIO_STEPS_START = 9000
SERGIO_STEPS_END = 7500
SERGIO_INTAKE_START = 3000.0
SERGIO_INTAKE_END = 3450.0
#: Cardio/exercise activity thermogenesis (Phase 3.1, F2) -- tapered down
#: as the bulk progresses, a plausible "less cardio, more lifting" pattern.
SERGIO_CARDIO_START = 300.0
SERGIO_CARDIO_END = 150.0
#: The most recent N weeks are logged at daily granularity with macros
#: (Phase 3.3/3.4, F6/F9), instead of Danel's all-weekly series, so the
#: seeded data also exercises mixed-granularity accounts and macro-based TEF.
SERGIO_DAILY_WEEKS = 4
#: A simple, illustrative protein/fat/carb split of each day's intake
#: (converted to grams via the standard Atwater factors) -- not tuned to
#: any account's own macro-target settings.
SERGIO_MACRO_SPLIT = {"protein": 0.30, "fat": 0.25, "carbs": 0.45}
#: Small deterministic day-to-day wiggle (Mon..Sun) so a daily-logged week
#: isn't perfectly flat; reused as a fraction of each field's own scale.
_DAILY_WIGGLE = (-0.2, 0.4, -0.4, 0.2, 0.0, -0.3, 0.3)


def _interpolate(start: float, end: float, fraction: float) -> float:
    return start + (end - start) * fraction


class LogManager:
    def __init__(
        self,
        log_dao: BodyLogDAO,
        audit_log_dao: Optional[AuditLogDAO] = None,
        metrics_cache=None,
    ):
        self.log_dao = log_dao
        self.audit_log_dao = audit_log_dao
        self.metrics_cache = metrics_cache

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
        cardio_kcal: float = 0.0,
        source: str = "real",
        granularity: str = "weekly",
        carbs_g: Optional[float] = None,
        fat_g: Optional[float] = None,
        protein_g: Optional[float] = None,
    ) -> BodyLog:
        _validate_granularity(granularity)
        candidate = LogInput(
            date=log_date,
            weight_kg=weight_kg,
            waist_cm=waist_cm,
            neck_cm=neck_cm,
            intake_kcal=intake_kcal,
            steps=steps,
            intake_is_real=intake_is_real,
            cardio_kcal=cardio_kcal,
            carbs_g=carbs_g,
            fat_g=fat_g,
            protein_g=protein_g,
        )
        validate_log_input(candidate)
        log = self.log_dao.create(
            user_id=user_id,
            date=log_date,
            weight_kg=weight_kg,
            waist_cm=waist_cm,
            neck_cm=neck_cm,
            intake_kcal=intake_kcal,
            intake_is_real=intake_is_real,
            steps=steps,
            cardio_kcal=cardio_kcal,
            source=source,
            granularity=granularity,
            carbs_g=carbs_g,
            fat_g=fat_g,
            protein_g=protein_g,
        )
        if self.metrics_cache is not None:
            self.metrics_cache.invalidate_for_user(user_id)
        return log

    def list_logs(self, user_id: int) -> List[BodyLog]:
        return self.log_dao.list_for_user(user_id)

    def get_log(self, log_id: int) -> Optional[BodyLog]:
        return self.log_dao.get_by_id(log_id)

    def update_log(self, log_id: int, **fields) -> Optional[BodyLog]:
        existing = self.log_dao.get_by_id(log_id)
        if existing is None:
            return None
        if "granularity" in fields:
            _validate_granularity(fields["granularity"])
        merged = LogInput(
            date=fields.get("date", existing.date),
            weight_kg=fields.get("weight_kg", existing.weight_kg),
            waist_cm=fields.get("waist_cm", existing.waist_cm),
            neck_cm=fields.get("neck_cm", existing.neck_cm),
            intake_kcal=fields.get("intake_kcal", existing.intake_kcal),
            steps=fields.get("steps", existing.steps),
            intake_is_real=fields.get("intake_is_real", existing.intake_is_real),
            cardio_kcal=fields.get("cardio_kcal", existing.cardio_kcal),
            carbs_g=fields.get("carbs_g", existing.carbs_g),
            fat_g=fields.get("fat_g", existing.fat_g),
            protein_g=fields.get("protein_g", existing.protein_g),
        )
        validate_log_input(merged)

        if self.audit_log_dao is not None:
            for field in LOG_EDITABLE_FIELDS:
                if field not in fields:
                    continue
                previous_value = getattr(existing, field)
                new_value = fields[field]
                if previous_value != new_value:
                    self.audit_log_dao.record(
                        user_id=existing.user_id,
                        entity_type="body_log",
                        entity_id=log_id,
                        field=field,
                        previous_value=str(previous_value),
                        new_value=str(new_value),
                    )

        updated = self.log_dao.update(log_id, **fields)
        if self.metrics_cache is not None:
            self.metrics_cache.invalidate_for_user(existing.user_id)
        return updated

    def delete_log(self, log_id: int) -> None:
        existing = self.log_dao.get_by_id(log_id)
        self.log_dao.delete(log_id)
        if existing is not None and self.metrics_cache is not None:
            self.metrics_cache.invalidate_for_user(existing.user_id)

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
                cardio_kcal=log.cardio_kcal,
                carbs_g=log.carbs_g,
                fat_g=log.fat_g,
                protein_g=log.protein_g,
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

    def seed_bulk_reference_series(self, user_id: int) -> List[BodyLog]:
        """Seed Sergio's bulk reference series (idempotent: no-op if the
        user already has logs). The most recent SERGIO_DAILY_WEEKS weeks
        are logged at daily granularity with macros, unlike Danel's
        all-weekly series above, so the seeded data also exercises F6/F9."""
        if self.log_dao.list_for_user(user_id):
            return []

        start = SERGIO_FIRST_LOG["date"]
        end = SERGIO_LAST_LOG["date"]
        total_weeks = (end - start).days // 7
        daily_from_week = total_weeks - SERGIO_DAILY_WEEKS + 1

        created: List[BodyLog] = []
        for week in range(total_weeks + 1):
            log_date = start + timedelta(days=7 * week)
            fraction = week / total_weeks
            weight_kg = _interpolate(
                SERGIO_FIRST_LOG["weight_kg"], SERGIO_LAST_LOG["weight_kg"], fraction
            )
            waist_cm = _interpolate(
                SERGIO_FIRST_LOG["waist_cm"], SERGIO_LAST_LOG["waist_cm"], fraction
            )
            neck_cm = _interpolate(
                SERGIO_FIRST_LOG["neck_cm"], SERGIO_LAST_LOG["neck_cm"], fraction
            )
            steps = _interpolate(SERGIO_STEPS_START, SERGIO_STEPS_END, fraction)
            intake_kcal = _interpolate(SERGIO_INTAKE_START, SERGIO_INTAKE_END, fraction)
            cardio_kcal = _interpolate(SERGIO_CARDIO_START, SERGIO_CARDIO_END, fraction)

            # The two boundary rows are reproduced exactly, same convention
            # as Danel's series above.
            if week == 0:
                weight_kg, waist_cm, neck_cm = (
                    SERGIO_FIRST_LOG["weight_kg"],
                    SERGIO_FIRST_LOG["waist_cm"],
                    SERGIO_FIRST_LOG["neck_cm"],
                )
            elif week == total_weeks:
                weight_kg, waist_cm, neck_cm = (
                    SERGIO_LAST_LOG["weight_kg"],
                    SERGIO_LAST_LOG["waist_cm"],
                    SERGIO_LAST_LOG["neck_cm"],
                )

            if week >= daily_from_week:
                created.extend(
                    self._seed_daily_week(
                        user_id,
                        log_date,
                        weight_kg,
                        waist_cm,
                        neck_cm,
                        intake_kcal,
                        steps,
                        cardio_kcal,
                    )
                )
            else:
                created.append(
                    self.create_log(
                        user_id=user_id,
                        log_date=log_date,
                        weight_kg=round(weight_kg, 1),
                        waist_cm=round(waist_cm, 1),
                        neck_cm=round(neck_cm, 1),
                        intake_kcal=round(intake_kcal, 2),
                        steps=round(steps),
                        cardio_kcal=round(cardio_kcal),
                        intake_is_real=True,
                        source="real",
                    )
                )
        return created

    def _seed_daily_week(
        self,
        user_id: int,
        week_date: date,
        weight_kg: float,
        waist_cm: float,
        neck_cm: float,
        intake_kcal: float,
        steps: float,
        cardio_kcal: float,
    ) -> List[BodyLog]:
        """The 7 days ending on ``week_date``, wiggled around that week's
        interpolated values, with macros split per SERGIO_MACRO_SPLIT."""
        created: List[BodyLog] = []
        for day_offset, wiggle in enumerate(_DAILY_WIGGLE):
            day = week_date - timedelta(days=6 - day_offset)
            day_intake = max(0.0, intake_kcal + wiggle * 40)
            protein_g = (day_intake * SERGIO_MACRO_SPLIT["protein"]) / 4.0
            fat_g = (day_intake * SERGIO_MACRO_SPLIT["fat"]) / 9.0
            carbs_g = (day_intake * SERGIO_MACRO_SPLIT["carbs"]) / 4.0
            created.append(
                self.create_log(
                    user_id=user_id,
                    log_date=day,
                    weight_kg=round(weight_kg + wiggle * 0.15, 1),
                    waist_cm=round(waist_cm, 1),
                    neck_cm=round(neck_cm, 1),
                    intake_kcal=round(day_intake, 2),
                    steps=round(max(0.0, steps + wiggle * 200)),
                    cardio_kcal=round(max(0.0, cardio_kcal + wiggle * 30)),
                    intake_is_real=True,
                    source="real",
                    granularity="daily",
                    carbs_g=round(carbs_g, 1),
                    fat_g=round(fat_g, 1),
                    protein_g=round(protein_g, 1),
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


def bulk_demo_profile_params() -> ProfileParams:
    return ProfileParams(
        height_cm=SERGIO_PROFILE.height_cm,
        sex=SERGIO_PROFILE.sex,
        birthdate=SERGIO_PROFILE.birthdate,
        target_bf=SERGIO_PROFILE.target_bf,
        weekly_rate=SERGIO_PROFILE.weekly_rate,
    )
