"""Historized daily activity-goal CRUD (Phase 10.2, see README): the same
create-new/deactivate-old/audit pattern as `GoalPlanManager`/
`EngineSettingsManager`, applied to a daily steps/cardio target instead of
the body-fat goal or engine constants. Unlike `GoalPlanManager`, there is
no coherence check to port over -- steps/cardio have no sign relationship
to body fat -- and unset (no active row) is the real default, matching
Phase 5.2's "don't force a goal at signup" precedent: no onboarding step
creates one.
"""

from __future__ import annotations

from datetime import date
from typing import List, Optional

from server.src.data.db.ActivityGoalDAO import ActivityGoalDAO
from server.src.data.db.AuditLogDAO import AuditLogDAO
from server.src.data.domain.ActivityGoal import ActivityGoal


class ActivityGoalManagerError(Exception):
    """Raised for invalid activity-goal parameters."""


class ActivityGoalManager:
    def __init__(
        self,
        activity_goal_dao: ActivityGoalDAO,
        audit_log_dao: Optional[AuditLogDAO] = None,
    ):
        self.activity_goal_dao = activity_goal_dao
        self.audit_log_dao = audit_log_dao

    def get_active(self, user_id: int) -> Optional[ActivityGoal]:
        return self.activity_goal_dao.get_active(user_id)

    def list_history(self, user_id: int) -> List[ActivityGoal]:
        return self.activity_goal_dao.list_for_user(user_id)

    def set_goal(
        self,
        user_id: int,
        steps_goal: Optional[float] = None,
        cardio_kcal_goal: Optional[float] = None,
        start_date: Optional[date] = None,
    ) -> ActivityGoal:
        if steps_goal is None and cardio_kcal_goal is None:
            raise ActivityGoalManagerError(
                "at least one of steps_goal/cardio_kcal_goal is required"
            )
        if steps_goal is not None and steps_goal <= 0:
            raise ActivityGoalManagerError("steps_goal must be positive")
        if cardio_kcal_goal is not None and cardio_kcal_goal <= 0:
            raise ActivityGoalManagerError("cardio_kcal_goal must be positive")

        previous = self.activity_goal_dao.get_active(user_id)
        if previous is not None:
            self.activity_goal_dao.deactivate(previous.activity_goal_id)
            if self.audit_log_dao is not None:
                self.audit_log_dao.record(
                    user_id=user_id,
                    entity_type="activity_goal",
                    entity_id=previous.activity_goal_id,
                    field="active",
                    previous_value="1",
                    new_value="0",
                )

        new_goal = self.activity_goal_dao.create(
            user_id=user_id,
            steps_goal=steps_goal,
            cardio_kcal_goal=cardio_kcal_goal,
            start_date=start_date or date.today(),
        )

        if self.audit_log_dao is not None:
            self.audit_log_dao.record(
                user_id=user_id,
                entity_type="activity_goal",
                entity_id=new_goal.activity_goal_id,
                field="steps_goal",
                previous_value=str(previous.steps_goal) if previous else None,
                new_value=str(steps_goal),
            )
            self.audit_log_dao.record(
                user_id=user_id,
                entity_type="activity_goal",
                entity_id=new_goal.activity_goal_id,
                field="cardio_kcal_goal",
                previous_value=str(previous.cardio_kcal_goal) if previous else None,
                new_value=str(cardio_kcal_goal),
            )

        return new_goal
