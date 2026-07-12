from __future__ import annotations

from datetime import date, datetime, timezone
from typing import List, Optional

from server.src.data.db.DB import DB
from server.src.data.domain.GoalPlan import GoalPlan


class GoalPlanDAO:
    def __init__(self, db: DB):
        self.db = db

    def create(
        self,
        *,
        user_id: int,
        target_bf: float,
        weekly_rate: float,
        direction: str,
        start_date: date,
        active: bool = True,
    ) -> GoalPlan:
        created_at = datetime.now(timezone.utc).isoformat()
        cursor = self.db.execute(
            """
            INSERT INTO goal_plans
                (user_id, target_bf, weekly_rate, direction, start_date, active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                target_bf,
                weekly_rate,
                direction,
                start_date.isoformat(),
                int(active),
                created_at,
            ),
        )
        return self.get_by_id(cursor.lastrowid)

    def get_by_id(self, goal_id: int) -> Optional[GoalPlan]:
        row = self.db.query_one("SELECT * FROM goal_plans WHERE goal_id = ?", (goal_id,))
        return GoalPlan.from_row(row) if row else None

    def get_active(self, user_id: int) -> Optional[GoalPlan]:
        row = self.db.query_one(
            """
            SELECT * FROM goal_plans
            WHERE user_id = ? AND active = 1
            ORDER BY start_date DESC, goal_id DESC
            LIMIT 1
            """,
            (user_id,),
        )
        return GoalPlan.from_row(row) if row else None

    def list_for_user(self, user_id: int) -> List[GoalPlan]:
        rows = self.db.query(
            """
            SELECT * FROM goal_plans
            WHERE user_id = ?
            ORDER BY start_date DESC, goal_id DESC
            """,
            (user_id,),
        )
        return [GoalPlan.from_row(row) for row in rows]

    def deactivate(self, goal_id: int) -> None:
        self.db.execute("UPDATE goal_plans SET active = 0 WHERE goal_id = ?", (goal_id,))

    def update_start_date(self, goal_id: int, new_start_date: date) -> None:
        self.db.execute(
            "UPDATE goal_plans SET start_date = ? WHERE goal_id = ?",
            (new_start_date.isoformat(), goal_id),
        )
