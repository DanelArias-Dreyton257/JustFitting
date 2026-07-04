from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from server.src.services.composition.models import CompositionResult


@dataclass(frozen=True)
class MetricsDTO:
    date: str
    age: int
    bmi: float
    ffmi: float
    ffmi_adj: float
    rfm: float
    navy: float
    deurenberg: float
    body_fat: float
    fat_mass_kg: float
    lean_mass_kg: float
    above_target: float
    bmr: float
    neat: float
    tdee: float
    target_calories: float
    intake_diff: float
    tef_kcal: float
    tef_mode: str
    weight_delta_kg: float
    weight_delta_pct: float
    weight_objective_kg: float
    weight_gap_kg: float
    weight_to_shed_kg: float
    weekly_deficit_kcal: float
    daily_deficit_kcal: float
    final_weight_kg: float
    weeks_to_goal: float
    source: str
    log_id: Optional[int] = None
    engine_version: Optional[int] = None

    @staticmethod
    def from_domain(
        result: CompositionResult,
        log_id: Optional[int] = None,
        engine_version: Optional[int] = None,
    ) -> "MetricsDTO":
        return MetricsDTO(
            date=result.date.isoformat(),
            age=result.age,
            bmi=result.bmi,
            ffmi=result.ffmi,
            ffmi_adj=result.ffmi_adj,
            rfm=result.rfm,
            navy=result.navy,
            deurenberg=result.deurenberg,
            body_fat=result.body_fat,
            fat_mass_kg=result.fat_mass_kg,
            lean_mass_kg=result.lean_mass_kg,
            above_target=result.above_target,
            bmr=result.bmr,
            neat=result.neat,
            tdee=result.tdee,
            target_calories=result.target_calories,
            intake_diff=result.intake_diff,
            tef_kcal=result.tef_kcal,
            tef_mode=result.tef_mode,
            weight_delta_kg=result.weight_delta_kg,
            weight_delta_pct=result.weight_delta_pct,
            weight_objective_kg=result.weight_objective_kg,
            weight_gap_kg=result.weight_gap_kg,
            weight_to_shed_kg=result.weight_to_shed_kg,
            weekly_deficit_kcal=result.weekly_deficit_kcal,
            daily_deficit_kcal=result.daily_deficit_kcal,
            final_weight_kg=result.final_weight_kg,
            weeks_to_goal=result.weeks_to_goal,
            source=result.source,
            log_id=log_id,
            engine_version=engine_version,
        )
