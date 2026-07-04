"""Pure, deterministic feedback detectors over an already-computed weekly
series -- turns guardrails that used to be a silent `warnings.warn` (or
didn't exist at all) into structured alerts the API/UI can surface.

Each detector only looks at fields `CompositionEngine.compute_row` already
produces (`weight_delta_pct`, `weight_delta_kg`, `weight_gap_kg`,
`fat_mass_kg`/`lean_mass_kg`), so this module adds no new computation to the
compute-order chain and needs no `ENGINE_VERSION` bump.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as date_type
from typing import List, Optional, Sequence

from server.src.data.domain.GoalPlan import GoalPlan
from server.src.services.composition import constants
from server.src.services.composition.EnergyReconciliation import EnergyReconciliationRow
from server.src.services.composition.GainQuality import GainQualityRow
from server.src.services.composition.models import (
    DEFAULT_ENGINE_CONSTANTS,
    CompositionResult,
    EngineConstants,
)


@dataclass(frozen=True)
class Alert:
    """A single user-facing feedback item anchored to one log's date."""

    type: str  # "implausible_change" | "stagnation" | "excessive_lean_loss" |
    # "deviation" | "bulk_rate_out_of_range" | "dirty_bulk" | "recalibrate"
    severity: str  # "warning" | "info"
    date: date_type
    message: str
    value: float
    threshold: float


def _implausible_change_alerts(
    results: Sequence[CompositionResult], thresholds: EngineConstants
) -> List[Alert]:
    alerts = []
    for result in results:
        if result.source != "real":
            continue
        if abs(result.weight_delta_pct) > thresholds.implausible_weekly_change_pct:
            alerts.append(
                Alert(
                    type="implausible_change",
                    severity="warning",
                    date=result.date,
                    message=(
                        f"Weight changed {result.weight_delta_pct:+.1%} in one week, "
                        "more than expected -- double-check this log."
                    ),
                    value=result.weight_delta_pct,
                    threshold=thresholds.implausible_weekly_change_pct,
                )
            )
    return alerts


def _stagnation_alerts(
    results: Sequence[CompositionResult], thresholds: EngineConstants
) -> List[Alert]:
    real_results = [r for r in results if r.source == "real"]
    alerts = []
    stagnation_weeks = thresholds.stagnation_weeks
    for i in range(stagnation_weeks - 1, len(real_results)):
        window = real_results[i - stagnation_weeks + 1 : i + 1]
        max_change = max(abs(r.weight_delta_kg) for r in window)
        if max_change <= thresholds.stagnation_threshold_kg:
            alerts.append(
                Alert(
                    type="stagnation",
                    severity="info",
                    date=window[-1].date,
                    message=(
                        f"Weight has moved less than {thresholds.stagnation_threshold_kg} kg "
                        f"for {stagnation_weeks} consecutive weeks -- possible plateau."
                    ),
                    value=max_change,
                    threshold=thresholds.stagnation_threshold_kg,
                )
            )
    return alerts


def _excessive_lean_loss_alerts(
    results: Sequence[CompositionResult], thresholds: EngineConstants
) -> List[Alert]:
    real_results = [r for r in results if r.source == "real"]
    alerts = []
    window_weeks = thresholds.lean_loss_window_weeks
    for i in range(window_weeks, len(real_results)):
        start, end = real_results[i - window_weeks], real_results[i]
        start_weight = start.fat_mass_kg + start.lean_mass_kg
        end_weight = end.fat_mass_kg + end.lean_mass_kg
        total_loss = start_weight - end_weight
        if total_loss <= 0:
            continue  # not a net loss over the window
        lean_loss = start.lean_mass_kg - end.lean_mass_kg
        share = lean_loss / total_loss
        if share > thresholds.max_lean_mass_loss_share:
            alerts.append(
                Alert(
                    type="excessive_lean_loss",
                    severity="warning",
                    date=end.date,
                    message=(
                        f"Lean mass made up {share:.0%} of the weight lost over the "
                        f"last {window_weeks} weeks -- consider more protein "
                        "or resistance training."
                    ),
                    value=share,
                    threshold=thresholds.max_lean_mass_loss_share,
                )
            )
    return alerts


def _deviation_alerts(
    results: Sequence[CompositionResult], thresholds: EngineConstants
) -> List[Alert]:
    alerts = []
    for result in results:
        if result.source != "real":
            continue
        if abs(result.weight_gap_kg) > thresholds.significant_deviation_kg:
            alerts.append(
                Alert(
                    type="deviation",
                    severity="info",
                    date=result.date,
                    message=(
                        f"Actual weight is {result.weight_gap_kg:+.2f} kg from this "
                        "week's objective."
                    ),
                    value=result.weight_gap_kg,
                    threshold=thresholds.significant_deviation_kg,
                )
            )
    return alerts


def _bulk_rate_alerts(goal: Optional[GoalPlan]) -> List[Alert]:
    """Flag (not block) a bulk goal whose weekly rate falls outside the
    recommended range (Phase 3, F1) -- a single, goal-level check, not a
    per-week one, so it's anchored to the goal's own `start_date`."""
    if goal is None or goal.direction != "bulk":
        return []
    if constants.BULK_RATE_MIN <= goal.weekly_rate <= constants.BULK_RATE_MAX:
        return []
    threshold = (
        constants.BULK_RATE_MAX
        if goal.weekly_rate > constants.BULK_RATE_MAX
        else constants.BULK_RATE_MIN
    )
    return [
        Alert(
            type="bulk_rate_out_of_range",
            severity="info",
            date=goal.start_date,
            message=(
                f"Weekly bulk rate {goal.weekly_rate:+.2%} is outside the "
                f"recommended {constants.BULK_RATE_MIN:.2%}-"
                f"{constants.BULK_RATE_MAX:.2%} range."
            ),
            value=goal.weekly_rate,
            threshold=threshold,
        )
    ]


def _dirty_bulk_alerts(
    gain_quality: Sequence[GainQualityRow],
    thresholds: EngineConstants,
    goal: Optional[GoalPlan],
) -> List[Alert]:
    """Flag (not block) a bulk week whose fat share of the gain exceeds the
    ideal ceiling (Phase 3.2, F5/F8) -- only meaningful for a bulk goal, and
    only on a genuine net-gain week (`fat_ratio` is `None` otherwise, see
    `GainQuality._safe_ratio`)."""
    if goal is None or goal.direction != "bulk":
        return []
    alerts = []
    for row in gain_quality:
        if row.fat_ratio is None or row.fat_ratio <= thresholds.fat_ratio_ideal:
            continue
        alerts.append(
            Alert(
                type="dirty_bulk",
                severity="info",
                date=row.date,
                message=(
                    f"This week's gain was {row.fat_ratio:.0%} fat, above the "
                    f"{thresholds.fat_ratio_ideal:.0%} ideal ceiling for a clean bulk."
                ),
                value=row.fat_ratio,
                threshold=thresholds.fat_ratio_ideal,
            )
        )
    return alerts


def _recalibrate_alerts(
    reconciliation: Sequence[EnergyReconciliationRow],
    thresholds: EngineConstants,
) -> List[Alert]:
    """Flag (not block) a week whose ingested-vs-tissue energy-balance error
    exceeds the configured threshold (Phase 3.2, F5) -- a persistently large
    gap suggests the energy model needs recalibrating for this account."""
    alerts = []
    for row in reconciliation:
        if row.error_kcal is None or row.error_kcal <= thresholds.reconciliation_error_threshold_kcal:
            continue
        alerts.append(
            Alert(
                type="recalibrate",
                severity="info",
                date=row.date,
                message=(
                    f"Energy-balance error was {row.error_kcal:.0f} kcal/day, above "
                    f"the {thresholds.reconciliation_error_threshold_kcal:.0f} kcal/day "
                    "threshold -- consider recalibrating your engine settings."
                ),
                value=row.error_kcal,
                threshold=thresholds.reconciliation_error_threshold_kcal,
            )
        )
    return alerts


def detect_alerts(
    results: Sequence[CompositionResult],
    thresholds: Optional[EngineConstants] = None,
    goal: Optional[GoalPlan] = None,
    gain_quality: Optional[Sequence[GainQualityRow]] = None,
    reconciliation: Optional[Sequence[EnergyReconciliationRow]] = None,
) -> List[Alert]:
    """Run every detector over a computed series, oldest first.

    ``results`` need not be pre-sorted or pre-filtered to real rows --
    each detector orders/filters what it needs. ``thresholds`` overrides
    the per-user alert thresholds (Phase 1.5); defaults to today's fixed
    `constants.py` values. ``goal`` is the account's active goal plan, used
    by the bulk-rate-range and dirty-bulk detectors (Phase 3/3.2); omitting
    it just skips those. ``gain_quality``/``reconciliation`` (Phase 3.2) feed
    the dirty-bulk/recalibrate detectors; omitting either just skips its
    detector.
    """
    thresholds = thresholds or DEFAULT_ENGINE_CONSTANTS
    ordered = sorted(results, key=lambda r: r.date)
    alerts = (
        _implausible_change_alerts(ordered, thresholds)
        + _stagnation_alerts(ordered, thresholds)
        + _excessive_lean_loss_alerts(ordered, thresholds)
        + _deviation_alerts(ordered, thresholds)
        + _bulk_rate_alerts(goal)
        + (_dirty_bulk_alerts(gain_quality, thresholds, goal) if gain_quality else [])
        + (_recalibrate_alerts(reconciliation, thresholds) if reconciliation else [])
    )
    return sorted(alerts, key=lambda a: a.date)
