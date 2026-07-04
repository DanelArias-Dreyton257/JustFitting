from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from server.src.services.composition.EnergyReconciliation import EnergyReconciliationRow


@dataclass(frozen=True)
class EnergyReconciliationDTO:
    date: str
    surplus_ingested_kcal: Optional[float]
    surplus_tissue_kcal: Optional[float]
    error_kcal: Optional[float]
    error_rolling_mean_kcal: Optional[float]
    error_threshold_kcal: float

    @staticmethod
    def from_domain(
        row: EnergyReconciliationRow, error_threshold_kcal: float
    ) -> "EnergyReconciliationDTO":
        return EnergyReconciliationDTO(
            date=row.date.isoformat(),
            surplus_ingested_kcal=row.surplus_ingested_kcal,
            surplus_tissue_kcal=row.surplus_tissue_kcal,
            error_kcal=row.error_kcal,
            error_rolling_mean_kcal=row.error_rolling_mean_kcal,
            error_threshold_kcal=error_threshold_kcal,
        )
