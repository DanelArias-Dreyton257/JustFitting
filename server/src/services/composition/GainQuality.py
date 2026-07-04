"""Gain-quality tracking (Phase 3.1, F3): the lean/fat partition of the
week-over-week weight *change*, not just the levels `CompositionResult`
already tracks. Pure post-processing over an already-computed series --
`delta_lean_kg + delta_fat_kg == weight_delta_kg` by construction, since
`lean_mass_kg + fat_mass_kg == weight_kg` for every row -- so this adds no
new base computation and needs no `ENGINE_VERSION` bump, mirroring how
`Alerts.py` derives feedback from an existing series instead of extending
the compute-order chain.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as date_type
from typing import List, Optional, Sequence

from server.src.services.composition.models import CompositionResult


@dataclass(frozen=True)
class GainQualityRow:
    """One row's lean/fat split of that week's change, plus the running
    cumulative split since the first row in the series."""

    date: date_type
    delta_lean_kg: float
    delta_fat_kg: float
    delta_lean_kg_cum: float
    delta_fat_kg_cum: float
    fat_ratio: Optional[float]  # None when weight_delta_kg == 0 (undefined)
    fat_ratio_cumulative: Optional[float]


#: Below this magnitude, a denominator is treated as zero -- guards against
#: floating-point noise (e.g. 18.3 - 18.0 + 71.7 - 72.0 landing on 2.8e-15
#: instead of exactly 0.0) producing a huge, meaningless ratio instead of
#: the intended `None` (undefined).
_ZERO_EPSILON = 1e-9


def _safe_ratio(numerator: float, denominator: float) -> Optional[float]:
    if abs(denominator) < _ZERO_EPSILON:
        return None
    return numerator / denominator


def compute_gain_quality(
    results: Sequence[CompositionResult],
) -> List[GainQualityRow]:
    """Walk a date-sorted series, diffing `lean_mass_kg`/`fat_mass_kg`
    against the previous row (base case 0 at the first row, same convention
    as `weight_delta_kg`), and accumulate a running cumulative split."""
    ordered = sorted(results, key=lambda r: r.date)
    rows: List[GainQualityRow] = []
    prev: Optional[CompositionResult] = None
    cum_lean = 0.0
    cum_fat = 0.0

    for result in ordered:
        delta_lean = result.lean_mass_kg - prev.lean_mass_kg if prev else 0.0
        delta_fat = result.fat_mass_kg - prev.fat_mass_kg if prev else 0.0
        cum_lean += delta_lean
        cum_fat += delta_fat

        rows.append(
            GainQualityRow(
                date=result.date,
                delta_lean_kg=delta_lean,
                delta_fat_kg=delta_fat,
                delta_lean_kg_cum=cum_lean,
                delta_fat_kg_cum=cum_fat,
                fat_ratio=_safe_ratio(delta_fat, delta_lean + delta_fat),
                fat_ratio_cumulative=_safe_ratio(cum_fat, cum_lean + cum_fat),
            )
        )
        prev = result

    return rows
