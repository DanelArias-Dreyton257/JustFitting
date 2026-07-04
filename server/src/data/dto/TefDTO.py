from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from server.src.services.composition.Tef import TefBreakdownRow


@dataclass(frozen=True)
class TefDTO:
    date: str
    has_macros: bool
    carbs_g: Optional[float]
    fat_g: Optional[float]
    protein_g: Optional[float]
    carb_kcal: Optional[float]
    fat_kcal: Optional[float]
    protein_kcal: Optional[float]
    tef_kcal_flat: float
    tef_kcal_macros: Optional[float]
    tef_mode_used: str

    @staticmethod
    def from_domain(row: TefBreakdownRow) -> "TefDTO":
        return TefDTO(
            date=row.date.isoformat(),
            has_macros=row.has_macros,
            carbs_g=row.carbs_g,
            fat_g=row.fat_g,
            protein_g=row.protein_g,
            carb_kcal=row.carb_kcal,
            fat_kcal=row.fat_kcal,
            protein_kcal=row.protein_kcal,
            tef_kcal_flat=row.tef_kcal_flat,
            tef_kcal_macros=row.tef_kcal_macros,
            tef_mode_used=row.tef_mode_used,
        )
