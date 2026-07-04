from __future__ import annotations

from dataclasses import dataclass

from server.src.data.domain.GoalPlan import GoalPlan


@dataclass(frozen=True)
class GoalPlanDTO:
    goal_id: int
    user_id: int
    target_bf: float
    weekly_rate: float
    direction: str
    start_date: str
    active: bool
    created_at: str

    @staticmethod
    def from_domain(goal: GoalPlan) -> "GoalPlanDTO":
        return GoalPlanDTO(
            goal_id=goal.goal_id,
            user_id=goal.user_id,
            target_bf=goal.target_bf,
            weekly_rate=goal.weekly_rate,
            direction=goal.direction,
            start_date=goal.start_date.isoformat(),
            active=goal.active,
            created_at=goal.created_at.isoformat(),
        )
