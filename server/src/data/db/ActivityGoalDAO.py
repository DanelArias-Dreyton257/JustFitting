from __future__ import annotations

from datetime import date, datetime, timezone
from typing import List, Optional

from server.src.data.db.DB import DB
from server.src.data.domain.ActivityGoal import ActivityGoal


class ActivityGoalDAO:
    def __init__(self, db: DB):
        self.db = db

    def create(
        self,
        *,
        user_id: int,
        steps_goal: Optional[float],
        cardio_kcal_goal: Optional[float],
        start_date: date,
        active: bool = True,
    ) -> ActivityGoal:
        created_at = datetime.now(timezone.utc).isoformat()
        cursor = self.db.execute(
            """
            INSERT INTO activity_goals
                (user_id, steps_goal, cardio_kcal_goal, start_date, active, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                steps_goal,
                cardio_kcal_goal,
                start_date.isoformat(),
                int(active),
                created_at,
            ),
        )
        return self.get_by_id(cursor.lastrowid)

    def get_by_id(self, activity_goal_id: int) -> Optional[ActivityGoal]:
        row = self.db.query_one(
            "SELECT * FROM activity_goals WHERE activity_goal_id = ?", (activity_goal_id,)
        )
        return ActivityGoal.from_row(row) if row else None

    def get_active(self, user_id: int) -> Optional[ActivityGoal]:
        row = self.db.query_one(
            """
            SELECT * FROM activity_goals
            WHERE user_id = ? AND active = 1
            ORDER BY start_date DESC, activity_goal_id DESC
            LIMIT 1
            """,
            (user_id,),
        )
        return ActivityGoal.from_row(row) if row else None

    def list_for_user(self, user_id: int) -> List[ActivityGoal]:
        rows = self.db.query(
            """
            SELECT * FROM activity_goals
            WHERE user_id = ?
            ORDER BY start_date DESC, activity_goal_id DESC
            """,
            (user_id,),
        )
        return [ActivityGoal.from_row(row) for row in rows]

    def deactivate(self, activity_goal_id: int) -> None:
        self.db.execute(
            "UPDATE activity_goals SET active = 0 WHERE activity_goal_id = ?",
            (activity_goal_id,),
        )
