"""Directly-computed thermic-effect-of-food from logged macronutrient grams
(Phase 3.4, F9) -- see docs/composition_spec.md's "Oleada 2" section, F9.

`compute_tef_kcal` is called directly by `CompositionEngine.compute_row`
(deciding *whether* to use it -- account `tef_mode` plus this week having
macros logged -- is the engine's job, not this module's).
`compute_tef_breakdown` is the read-side view behind `GET /api/metrics/tef`:
for every week it recomputes what the flat/divisor estimate *would* have
been, alongside the macro breakdown when available, regardless of which one
a given row actually applied -- mirroring how `EnergyReconciliation.py` and
`GainQuality.py` are pure read-side views over an already-computed series.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as date_type
from typing import List, Optional, Protocol, Sequence

from server.src.services.composition.models import (
    DEFAULT_ENGINE_CONSTANTS,
    CompositionResult,
    EngineConstants,
)


def compute_tef_kcal(
    carbs_g: float,
    fat_g: float,
    protein_g: float,
    kappa_carbs: float,
    kappa_fat: float,
    kappa_protein: float,
) -> float:
    """`TEF = kappa_carbs*carbs_g + kappa_fat*fat_g + kappa_protein*protein_g`.

    Linear in each macro, so this is identical whether the grams passed in
    are a single day's or a week's mean grams (see `LogResampler`'s
    mean-of-logged-days convention for macros) -- the mean of daily TEF
    values equals the TEF of the mean macros.
    """
    return kappa_carbs * carbs_g + kappa_fat * fat_g + kappa_protein * protein_g


class _LogLike(Protocol):
    """The `BodyLog` fields this module reads."""

    date: date_type
    cardio_kcal: float
    carbs_g: Optional[float]
    fat_g: Optional[float]
    protein_g: Optional[float]


@dataclass(frozen=True)
class TefBreakdownRow:
    """One week's TEF: the flat/divisor estimate (always computable, for
    comparison) alongside the macro breakdown when this week has grams
    logged. `tef_mode_used` mirrors the actual `CompositionResult.tef_mode`
    for this week -- macros only apply when both the account's `tef_mode`
    setting and this week's macros are available.
    """

    date: date_type
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


def compute_tef_breakdown(
    logs: Sequence[_LogLike],
    results: Sequence[CompositionResult],
    engine_constants: Optional[EngineConstants] = None,
) -> List[TefBreakdownRow]:
    """``logs`` and ``results`` must be the same chronological series (one
    log per result, e.g. as produced by `MetricsSeriesService`)."""
    ec = engine_constants or DEFAULT_ENGINE_CONSTANTS
    ordered = sorted(zip(logs, results), key=lambda pair: pair[1].date)

    rows: List[TefBreakdownRow] = []
    for log, result in ordered:
        has_macros = (
            log.carbs_g is not None
            and log.fat_g is not None
            and log.protein_g is not None
        )
        tef_flat = ec.tef * (result.bmr + result.neat + log.cardio_kcal) / (1 - ec.tef)

        carb_kcal = fat_kcal = protein_kcal = tef_macros = None
        if has_macros:
            carb_kcal = ec.kappa_carbs * log.carbs_g
            fat_kcal = ec.kappa_fat * log.fat_g
            protein_kcal = ec.kappa_protein * log.protein_g
            tef_macros = carb_kcal + fat_kcal + protein_kcal

        rows.append(
            TefBreakdownRow(
                date=result.date,
                has_macros=has_macros,
                carbs_g=log.carbs_g,
                fat_g=log.fat_g,
                protein_g=log.protein_g,
                carb_kcal=carb_kcal,
                fat_kcal=fat_kcal,
                protein_kcal=protein_kcal,
                tef_kcal_flat=tef_flat,
                tef_kcal_macros=tef_macros,
                tef_mode_used=result.tef_mode,
            )
        )

    return rows
