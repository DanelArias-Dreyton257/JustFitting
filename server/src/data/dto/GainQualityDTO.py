from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from server.src.services.composition.GainQuality import GainQualityRow


@dataclass(frozen=True)
class GainQualityDTO:
    date: str
    delta_lean_kg: float
    delta_fat_kg: float
    delta_lean_kg_cum: float
    delta_fat_kg_cum: float
    fat_ratio: Optional[float]
    fat_ratio_cumulative: Optional[float]
    fat_ratio_ideal: float

    @staticmethod
    def from_domain(row: GainQualityRow, fat_ratio_ideal: float) -> "GainQualityDTO":
        return GainQualityDTO(
            date=row.date.isoformat(),
            delta_lean_kg=row.delta_lean_kg,
            delta_fat_kg=row.delta_fat_kg,
            delta_lean_kg_cum=row.delta_lean_kg_cum,
            delta_fat_kg_cum=row.delta_fat_kg_cum,
            fat_ratio=row.fat_ratio,
            fat_ratio_cumulative=row.fat_ratio_cumulative,
            fat_ratio_ideal=fat_ratio_ideal,
        )
