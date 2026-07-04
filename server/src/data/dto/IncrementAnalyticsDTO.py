from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from server.src.services.composition.IncrementAnalytics import IncrementAnalyticsRow


@dataclass(frozen=True)
class IncrementAnalyticsDTO:
    date: str
    incr_real_pct: float
    incr_real_mean_pct: float
    deviation_pct: Optional[float]
    goal_weekly_rate: float

    @staticmethod
    def from_domain(
        row: IncrementAnalyticsRow, goal_weekly_rate: float
    ) -> "IncrementAnalyticsDTO":
        return IncrementAnalyticsDTO(
            date=row.date.isoformat(),
            incr_real_pct=row.incr_real_pct,
            incr_real_mean_pct=row.incr_real_mean_pct,
            deviation_pct=row.deviation_pct,
            goal_weekly_rate=goal_weekly_rate,
        )
