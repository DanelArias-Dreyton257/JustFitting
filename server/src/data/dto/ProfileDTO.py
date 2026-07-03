from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from server.src.data.domain.GoalPlan import GoalPlan
from server.src.data.domain.UserProfile import UserProfile


@dataclass(frozen=True)
class ProfileDTO:
    user_id: int
    username: str
    email: str
    height_cm: float
    sex: int
    birthdate: str
    target_bf: Optional[float]
    weekly_rate: Optional[float]
    direction: Optional[str]
    units: str
    created_at: str

    @staticmethod
    def from_domain(
        profile: UserProfile, goal: Optional[GoalPlan] = None
    ) -> "ProfileDTO":
        return ProfileDTO(
            user_id=profile.user_id,
            username=profile.username,
            email=profile.email,
            height_cm=profile.height_cm,
            sex=profile.sex,
            birthdate=profile.birthdate.isoformat(),
            target_bf=goal.target_bf if goal else None,
            weekly_rate=goal.weekly_rate if goal else None,
            direction=goal.direction if goal else None,
            units=profile.units,
            created_at=profile.created_at.isoformat(),
        )
