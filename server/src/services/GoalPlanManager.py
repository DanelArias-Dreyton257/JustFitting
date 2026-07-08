"""Historized goal-plan CRUD: every target-BF/weekly-rate change creates a
new `GoalPlan` row and deactivates the previous one, instead of overwriting
`target_bf`/`weekly_rate` in place.
"""

from __future__ import annotations

from datetime import date
from typing import List, Optional

from server.src.data.db.AuditLogDAO import AuditLogDAO
from server.src.data.db.GoalPlanDAO import GoalPlanDAO
from server.src.data.domain.GoalPlan import GoalPlan
from server.src.data.domain.UserProfile import UserProfile
from server.src.services.composition.models import ProfileParams


class GoalPlanManagerError(Exception):
    """Raised for invalid goal-plan parameters."""


class GoalPlanManager:
    def __init__(
        self,
        goal_plan_dao: GoalPlanDAO,
        audit_log_dao: Optional[AuditLogDAO] = None,
        metrics_cache=None,
    ):
        self.goal_plan_dao = goal_plan_dao
        self.audit_log_dao = audit_log_dao
        self.metrics_cache = metrics_cache

    def create_goal_plan(
        self,
        user_id: int,
        target_bf: float,
        weekly_rate: float,
        start_date: Optional[date] = None,
    ) -> GoalPlan:
        if not (0 < target_bf < 1):
            raise GoalPlanManagerError("target_bf must be a fraction between 0 and 1")

        previous = self.goal_plan_dao.get_active(user_id)
        if previous is not None:
            self.goal_plan_dao.deactivate(previous.goal_id)
            if self.audit_log_dao is not None:
                self.audit_log_dao.record(
                    user_id=user_id,
                    entity_type="goal_plan",
                    entity_id=previous.goal_id,
                    field="active",
                    previous_value="1",
                    new_value="0",
                )

        new_plan = self.goal_plan_dao.create(
            user_id=user_id,
            target_bf=target_bf,
            weekly_rate=weekly_rate,
            start_date=start_date or date.today(),
        )

        if self.audit_log_dao is not None:
            self.audit_log_dao.record(
                user_id=user_id,
                entity_type="goal_plan",
                entity_id=new_plan.goal_id,
                field="target_bf",
                previous_value=str(previous.target_bf) if previous else None,
                new_value=str(target_bf),
            )
            self.audit_log_dao.record(
                user_id=user_id,
                entity_type="goal_plan",
                entity_id=new_plan.goal_id,
                field="weekly_rate",
                previous_value=str(previous.weekly_rate) if previous else None,
                new_value=str(weekly_rate),
            )

        if self.metrics_cache is not None:
            self.metrics_cache.invalidate_for_user(user_id)

        return new_plan

    def get_active(self, user_id: int) -> Optional[GoalPlan]:
        return self.goal_plan_dao.get_active(user_id)

    def list_history(self, user_id: int) -> List[GoalPlan]:
        return self.goal_plan_dao.list_for_user(user_id)

    def active_period_start(self, user_id: int) -> Optional[date]:
        """The date derived series/projections should be scoped from
        (Phase 5.3), or `None` to mean "don't scope, use everything."

        Returns `None` whenever there's nothing to exclude: no active goal,
        or the account has never changed its goal (`list_history` length
        <= 1). Every account's very first goal is created with
        `start_date=date.today()` at registration (`UserManager.register`),
        so naively filtering to `date >= active_goal.start_date`
        unconditionally would drop any log dated before signup -- including
        a same-day backdated entry -- even for an account that has never
        touched its goal. Only once a goal change has actually happened
        (a second `goal_plans` row exists) is there a genuinely different
        prior period to exclude.
        """
        goal = self.get_active(user_id)
        if goal is None or len(self.list_history(user_id)) <= 1:
            return None
        return goal.start_date

    @staticmethod
    def build_profile_params(profile: UserProfile, goal: GoalPlan) -> ProfileParams:
        return ProfileParams(
            height_cm=profile.height_cm,
            sex=profile.sex,
            birthdate=profile.birthdate,
            target_bf=goal.target_bf,
            weekly_rate=goal.weekly_rate,
        )
