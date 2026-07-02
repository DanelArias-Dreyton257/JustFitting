"""Historized goal configuration (target body-fat %, weekly rate).

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
            start_date=date.fromisoformat(row["start_date"]),
            active=bool(row["active"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )
