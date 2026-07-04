"""Energy reconciliation (Phase 3.2, F5): compares the surplus/deficit
implied by logged intake against the surplus/deficit implied by the
*following* week's measured tissue change, surfacing the gap as an
a-posteriori validation of the energy model.

Inherently one-week-lagged: `Error_i` needs week `i+1`'s fat/lean deltas, so
the most recently logged week never has one yet -- not a same-week metric.
Reuses `GainQuality.compute_gain_quality` for those deltas rather than
re-deriving them, mirroring how `Alerts.py`/`GainQuality.py` are pure
read-side views over an already-computed series (no `ENGINE_VERSION` bump).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as date_type
from typing import List, Optional, Protocol, Sequence

from server.src.services.composition import constants
from server.src.services.composition.GainQuality import compute_gain_quality
from server.src.services.composition.models import DEFAULT_ENGINE_CONSTANTS, CompositionResult, EngineConstants


class _LogLike(Protocol):
    """The only two `BodyLog` fields this module reads."""

    date: date_type
    intake_kcal: float
    intake_is_real: bool


@dataclass(frozen=True)
class EnergyReconciliationRow:
    """One week's ingested-vs-tissue energy-balance comparison.

    `surplus_tissue_kcal`/`error_kcal` are `None` for the most recent week
    (no next week's deltas yet) and `surplus_ingested_kcal`/`error_kcal` are
    `None` for a week with only assumed (not real) intake logged.
    """

    date: date_type
    surplus_ingested_kcal: Optional[float]
    surplus_tissue_kcal: Optional[float]
    error_kcal: Optional[float]
    error_rolling_mean_kcal: Optional[float]


def compute_energy_reconciliation(
    logs: Sequence[_LogLike],
    results: Sequence[CompositionResult],
    engine_constants: Optional[EngineConstants] = None,
    window_weeks: int = constants.ENERGY_RECONCILIATION_WINDOW_WEEKS,
) -> List[EnergyReconciliationRow]:
    """``logs`` and ``results`` must be the same chronological series (one
    log per result, e.g. as produced by `MetricsSeriesService`)."""
    ec = engine_constants or DEFAULT_ENGINE_CONSTANTS
    ordered = sorted(zip(logs, results), key=lambda pair: pair[1].date)
    ordered_results = [result for _, result in ordered]
    gain_quality_rows = compute_gain_quality(ordered_results)

    rows: List[EnergyReconciliationRow] = []
    recent_errors: List[float] = []
    for i, (log, result) in enumerate(ordered):
        surplus_ingested = (
            log.intake_kcal - result.tdee if log.intake_is_real else None
        )

        surplus_tissue: Optional[float] = None
        error: Optional[float] = None
        if i + 1 < len(ordered):
            next_gq = gain_quality_rows[i + 1]
            surplus_tissue = (
                next_gq.delta_fat_kg * ec.kcal_per_kg_fat
                + next_gq.delta_lean_kg * ec.lean_tissue_kcal_per_kg
            ) / constants.DAYS_PER_WEEK
            if surplus_ingested is not None:
                error = abs(surplus_ingested - surplus_tissue)

        if error is not None:
            recent_errors.append(error)
        window = recent_errors[-window_weeks:] if window_weeks > 0 else recent_errors
        rolling_mean = sum(window) / len(window) if window else None

        rows.append(
            EnergyReconciliationRow(
                date=result.date,
                surplus_ingested_kcal=surplus_ingested,
                surplus_tissue_kcal=surplus_tissue,
                error_kcal=error,
                error_rolling_mean_kcal=rolling_mean,
            )
        )

    return rows
