"""Evidence-based per-account macro targets (Phase 3.4 extension, beyond the
`docs/JustFitting_TEF_Macronutrientes.pdf` source doc): protein and fat
targets are set directly as grams per kg body mass; carbs are the
"remainder of calories" once protein/fat's kcal share (standard Atwater
conversion) is subtracted from that week's `target_calories` -- there's no
carbs-per-kg constant, mirroring how the source doc itself treats carbs as
a remainder rather than an independently-set target.

Commonly-cited sports-nutrition ranges are roughly 1.6-2.2 g/kg protein and
0.5-0.8 g/kg fat for a cut, and 1.5-2.0 g/kg protein and 0.7-1.0 g/kg fat
for a bulk; `EngineConstants.protein_target_g_per_kg`/`fat_target_g_per_kg`
default to a single mid-point (1.75/0.70) inside both ranges, tunable per
account like every other engine constant.

Pure read-side view over an already-computed series -- like `GainQuality`/
`EnergyReconciliation`, this adds no new base computation and needs no
`ENGINE_VERSION` bump.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as date_type
from typing import List, Optional, Protocol, Sequence

from server.src.services.composition import constants
from server.src.services.composition.models import (
    DEFAULT_ENGINE_CONSTANTS,
    CompositionResult,
    EngineConstants,
)


class _LogLike(Protocol):
    """The `BodyLog` fields this module reads."""

    date: date_type
    weight_kg: float
    carbs_g: Optional[float]
    fat_g: Optional[float]
    protein_g: Optional[float]


@dataclass(frozen=True)
class MacroTargetsRow:
    """One week's macro targets (always computable from that week's weight
    and target_calories) alongside the actual logged grams/kcal, when this
    week has macros logged."""

    date: date_type
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


def compute_macro_targets(
    logs: Sequence[_LogLike],
    results: Sequence[CompositionResult],
    engine_constants: Optional[EngineConstants] = None,
) -> List[MacroTargetsRow]:
    """``logs`` and ``results`` must be the same chronological series (one
    log per result, e.g. as produced by `MetricsSeriesService`)."""
    ec = engine_constants or DEFAULT_ENGINE_CONSTANTS
    ordered = sorted(zip(logs, results), key=lambda pair: pair[1].date)

    rows: List[MacroTargetsRow] = []
    for log, result in ordered:
        protein_target_g = ec.protein_target_g_per_kg * log.weight_kg
        fat_target_g = ec.fat_target_g_per_kg * log.weight_kg
        protein_target_kcal = protein_target_g * constants.ATWATER_PROTEIN_KCAL_PER_G
        fat_target_kcal = fat_target_g * constants.ATWATER_FAT_KCAL_PER_G
        carbs_target_kcal = max(
            0.0, result.target_calories - protein_target_kcal - fat_target_kcal
        )
        carbs_target_g = carbs_target_kcal / constants.ATWATER_CARB_KCAL_PER_G

        has_actual = (
            log.carbs_g is not None
            and log.fat_g is not None
            and log.protein_g is not None
        )
        protein_actual_kcal = fat_actual_kcal = carbs_actual_kcal = None
        if has_actual:
            protein_actual_kcal = log.protein_g * constants.ATWATER_PROTEIN_KCAL_PER_G
            fat_actual_kcal = log.fat_g * constants.ATWATER_FAT_KCAL_PER_G
            carbs_actual_kcal = log.carbs_g * constants.ATWATER_CARB_KCAL_PER_G

        rows.append(
            MacroTargetsRow(
                date=result.date,
                protein_target_g=protein_target_g,
                fat_target_g=fat_target_g,
                carbs_target_g=carbs_target_g,
                protein_target_kcal=protein_target_kcal,
                fat_target_kcal=fat_target_kcal,
                carbs_target_kcal=carbs_target_kcal,
                has_actual=has_actual,
                protein_actual_g=log.protein_g,
                fat_actual_g=log.fat_g,
                carbs_actual_g=log.carbs_g,
                protein_actual_kcal=protein_actual_kcal,
                fat_actual_kcal=fat_actual_kcal,
                carbs_actual_kcal=carbs_actual_kcal,
            )
        )

    return rows
