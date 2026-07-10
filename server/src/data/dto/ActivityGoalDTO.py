from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from server.src.data.domain.ActivityGoal import ActivityGoal


@dataclass(frozen=True)
class ActivityGoalDTO:
    is_set: bool
    steps_goal: Optional[float] = None
    cardio_kcal_goal: Optional[float] = None
    activity_goal_id: Optional[int] = None
    start_date: Optional[str] = None
    active: Optional[bool] = None
    created_at: Optional[str] = None

    @staticmethod
    def from_domain(goal: Optional[ActivityGoal]) -> "ActivityGoalDTO":
        if goal is None:
            return ActivityGoalDTO(is_set=False)
        return ActivityGoalDTO(
            is_set=True,
            steps_goal=goal.steps_goal,
            cardio_kcal_goal=goal.cardio_kcal_goal,
            activity_goal_id=goal.activity_goal_id,
            start_date=goal.start_date.isoformat(),
            active=goal.active,
            created_at=goal.created_at.isoformat(),
        )
