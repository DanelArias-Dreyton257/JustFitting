"""Historized daily activity goal (steps/cardio) -- Phase 10.2 (Today
dashboard section, see README). Independent of the main body-fat
``GoalPlan``: it has no direction/coherence rules, and starts unset
(``ActivityGoalManager.get_active`` returns ``None``) rather than
defaulting to anything, unlike a brand-new account's goal plan.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional


@dataclass
class ActivityGoal:
    activity_goal_id: int
    user_id: int
    steps_goal: Optional[float]
    cardio_kcal_goal: Optional[float]
    start_date: date
    active: bool
    created_at: datetime

    @staticmethod
    def from_row(row) -> "ActivityGoal":
        return ActivityGoal(
            activity_goal_id=row["activity_goal_id"],
            user_id=row["user_id"],
            steps_goal=row["steps_goal"],
            cardio_kcal_goal=row["cardio_kcal_goal"],
            start_date=date.fromisoformat(row["start_date"]),
            active=bool(row["active"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )
