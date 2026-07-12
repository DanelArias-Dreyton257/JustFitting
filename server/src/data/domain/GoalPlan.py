"""Historized goal configuration (target body-fat %, weekly rate,
direction).

Replaces the single mutable ``target_bf``/``weekly_rate`` pair that used to
live directly on ``users``: each change creates a new row and deactivates
the previous one, so a user's goal history survives across changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass
class GoalPlan:
    goal_id: int
    user_id: int
    target_bf: float
    weekly_rate: float
    #: "cut" | "bulk" -- explicit and user-chosen when the goal is created
    #: (Phase 12.1), stored on ``goal_plans.direction``. Before Phase 12 this
    #: was a derived ``@property`` ("bulk" for a positive weekly rate, "cut"
    #: otherwise, no stored column) -- see
    #: ``docs/composition_spec.md``'s "Phase 12" section for why an explicit,
    #: stored field replaced the inference (it still must agree with
    #: ``weekly_rate``'s sign wherever that sign is meaningful --
    #: ``GoalPlanManager.check_direction_matches_rate`` enforces it -- except
    #: the ``weekly_rate == 0`` placeholder/maintenance case, which has no
    #: sign to check against).
    direction: str
    start_date: date
    active: bool
    created_at: datetime

    @staticmethod
    def from_row(row) -> "GoalPlan":
        return GoalPlan(
            goal_id=row["goal_id"],
            user_id=row["user_id"],
            target_bf=row["target_bf"],
            weekly_rate=row["weekly_rate"],
            direction=row["direction"],
            start_date=date.fromisoformat(row["start_date"]),
            active=bool(row["active"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )
