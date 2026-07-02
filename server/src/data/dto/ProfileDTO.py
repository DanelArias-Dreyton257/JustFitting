from __future__ import annotations

from dataclasses import dataclass

from server.src.data.domain.UserProfile import UserProfile


@dataclass(frozen=True)
class ProfileDTO:
    user_id: int
    username: str
    email: str
    height_cm: float
    sex: int
    birthdate: str
    target_bf: float
    weekly_rate: float
    units: str
    created_at: str

    @staticmethod
    def from_domain(profile: UserProfile) -> "ProfileDTO":
        return ProfileDTO(
            user_id=profile.user_id,
            username=profile.username,
            email=profile.email,
            height_cm=profile.height_cm,
            sex=profile.sex,
            birthdate=profile.birthdate.isoformat(),
            target_bf=profile.target_bf,
            weekly_rate=profile.weekly_rate,
            units=profile.units,
            created_at=profile.created_at.isoformat(),
        )
