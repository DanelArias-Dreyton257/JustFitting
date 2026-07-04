from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from server.src.services.composition.MacroTargets import MacroTargetsRow


@dataclass(frozen=True)
class MacroTargetsDTO:
    date: str
    protein_target_g: float
    fat_target_g: float
    carbs_target_g: float
    protein_target_kcal: float
    fat_target_kcal: float
    carbs_target_kcal: float
    has_actual: bool
    protein_actual_g: Optional[float]
    fat_actual_g: Optional[float]
    carbs_actual_g: Optional[float]
    protein_actual_kcal: Optional[float]
    fat_actual_kcal: Optional[float]
    carbs_actual_kcal: Optional[float]

    @staticmethod
    def from_domain(row: MacroTargetsRow) -> "MacroTargetsDTO":
        return MacroTargetsDTO(
            date=row.date.isoformat(),
            protein_target_g=row.protein_target_g,
            fat_target_g=row.fat_target_g,
            carbs_target_g=row.carbs_target_g,
            protein_target_kcal=row.protein_target_kcal,
            fat_target_kcal=row.fat_target_kcal,
            carbs_target_kcal=row.carbs_target_kcal,
            has_actual=row.has_actual,
            protein_actual_g=row.protein_actual_g,
            fat_actual_g=row.fat_actual_g,
            carbs_actual_g=row.carbs_actual_g,
            protein_actual_kcal=row.protein_actual_kcal,
            fat_actual_kcal=row.fat_actual_kcal,
            carbs_actual_kcal=row.carbs_actual_kcal,
        )
