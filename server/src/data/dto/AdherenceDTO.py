from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class AdherenceDTO:
    mean_intake_diff_kcal: Optional[float]
    real_log_count: int

    @staticmethod
    def from_values(
        mean_intake_diff_kcal: Optional[float], real_log_count: int
    ) -> "AdherenceDTO":
        return AdherenceDTO(
            mean_intake_diff_kcal=mean_intake_diff_kcal,
            real_log_count=real_log_count,
        )
