from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from server.src.services.composition.TodayEstimate import TodayEstimateRow


@dataclass(frozen=True)
class TodayEstimateDTO:
    date: str
    is_current: bool
    steps: Optional[float]
    intake_kcal: Optional[float]
    cardio_kcal: Optional[float]
    target_calories: Optional[float]
    kcal_to_target: Optional[float]
    neat_kcal: Optional[float]
    tef_kcal: Optional[float]
    tef_mode: Optional[str]
    eat_kcal: Optional[float]
    steps_goal: Optional[float]
    cardio_kcal_goal: Optional[float]
    steps_left: Optional[float]
    cardio_left: Optional[float]

    @staticmethod
    def from_domain(row: TodayEstimateRow) -> "TodayEstimateDTO":
        return TodayEstimateDTO(
            date=row.date.isoformat(),
            is_current=row.is_current,
            steps=row.steps,
            intake_kcal=row.intake_kcal,
            cardio_kcal=row.cardio_kcal,
            target_calories=row.target_calories,
            kcal_to_target=row.kcal_to_target,
            neat_kcal=row.neat_kcal,
            tef_kcal=row.tef_kcal,
            tef_mode=row.tef_mode,
            eat_kcal=row.eat_kcal,
            steps_goal=row.steps_goal,
            cardio_kcal_goal=row.cardio_kcal_goal,
            steps_left=row.steps_left,
            cardio_left=row.cardio_left,
        )
