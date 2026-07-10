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


#: Phase 8.2: a target_bf within this many percentage points (as a fraction)
#: of the account's current body fat is treated as maintenance/recomp --
#: any weekly_rate is coherent with it, since neither "losing" nor "gaining"
#: cleanly describes staying at roughly the same body fat.
BODY_FAT_COHERENCE_EPSILON = 0.005


def check_goal_coherence(
    current_bf: Optional[float], target_bf: float, weekly_rate: float
) -> None:
    """Sign-coherence check between a candidate goal and the account's
    actual current body fat (Phase 8.2): a fat-loss target (`target_bf`
    below current) paired with a bulk rate (`weekly_rate > 0`), or a
    fat-gain target paired with a cut rate (`weekly_rate < 0`), is
    self-contradictory and rejected. `current_bf=None` (no computable log
    yet, e.g. a brand-new default goal) skips the check entirely -- there's
    nothing yet to compare against. This checks sign coherence only, not
    magnitude (see README's Phase 8.2/Phase 11.4 notes for the bulk/cut
    magnitude checks that already exist/are planned separately).
    """
    if current_bf is None:
        return
    if abs(target_bf - current_bf) <= BODY_FAT_COHERENCE_EPSILON:
        return
    if target_bf < current_bf and weekly_rate > 0:
        raise GoalPlanManagerError(
            "target_bf is below your current body fat (a fat-loss target), "
            "but weekly_rate is positive (a bulk rate) -- a cut target needs "
            "weekly_rate <= 0"
        )
    if target_bf > current_bf and weekly_rate < 0:
        raise GoalPlanManagerError(
            "target_bf is above your current body fat (a fat-gain target), "
            "but weekly_rate is negative (a cut rate) -- a bulk target needs "
            "weekly_rate >= 0"
        )


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
        current_bf: Optional[float] = None,
    ) -> GoalPlan:
        if not (0 < target_bf < 1):
            raise GoalPlanManagerError("target_bf must be a fraction between 0 and 1")
        check_goal_coherence(current_bf, target_bf, weekly_rate)

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

    def update_start_date(self, user_id: int, new_start_date: date) -> GoalPlan:
        """Retroactively corrects when the *currently active* goal actually
        began (Phase 8.1) -- mutates its `start_date` in place rather than
        creating a new historized row, since this is correcting a fact about
        the same goal, not changing the goal itself. Lets a user who was
        already mid-cut/mid-bulk before adopting JustFitting backdate their
        current goal's period so already-logged history counts toward it
        (see `active_period_start`'s docstring for why that scoping matters).
        """
        active = self.goal_plan_dao.get_active(user_id)
        if active is None:
            raise GoalPlanManagerError("no active goal plan")
        if new_start_date > date.today():
            raise GoalPlanManagerError("start_date cannot be in the future")

        previous = None
        for goal in self.list_history(user_id):
            if goal.goal_id == active.goal_id:
                continue
            if previous is None or goal.start_date > previous.start_date:
                previous = goal
        if previous is not None and new_start_date <= previous.start_date:
            raise GoalPlanManagerError(
                "start_date must be strictly after the previous goal's start "
                f"date ({previous.start_date.isoformat()})"
            )

        old_start_date = active.start_date
        self.goal_plan_dao.update_start_date(active.goal_id, new_start_date)

        if self.audit_log_dao is not None:
            self.audit_log_dao.record(
                user_id=user_id,
                entity_type="goal_plan",
                entity_id=active.goal_id,
                field="start_date",
                previous_value=old_start_date.isoformat(),
                new_value=new_start_date.isoformat(),
            )

        if self.metrics_cache is not None:
            self.metrics_cache.invalidate_for_user(user_id)

        return self.goal_plan_dao.get_by_id(active.goal_id)

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
