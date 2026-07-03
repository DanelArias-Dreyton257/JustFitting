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
from typing import List, Sequence

from server.src.services.composition import CompositionEngine
from server.src.services.composition.constants import (
    LEAN_LOSS_WINDOW_WEEKS,
    MAX_LEAN_MASS_LOSS_SHARE,
    SIGNIFICANT_DEVIATION_KG,
    STAGNATION_THRESHOLD_KG,
    STAGNATION_WEEKS,
)
from server.src.services.composition.models import CompositionResult


@dataclass(frozen=True)
class Alert:
    """A single user-facing feedback item anchored to one log's date."""

    type: str  # "implausible_change" | "stagnation" | "excessive_lean_loss" | "deviation"
    severity: str  # "warning" | "info"
    date: date_type
    message: str
    value: float
    threshold: float


def _implausible_change_alerts(results: Sequence[CompositionResult]) -> List[Alert]:
    alerts = []
    for result in results:
        if result.source != "real":
            continue
        if abs(result.weight_delta_pct) > CompositionEngine.IMPLAUSIBLE_WEEKLY_CHANGE_PCT:
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
                    threshold=CompositionEngine.IMPLAUSIBLE_WEEKLY_CHANGE_PCT,
                )
            )
    return alerts


def _stagnation_alerts(results: Sequence[CompositionResult]) -> List[Alert]:
    real_results = [r for r in results if r.source == "real"]
    alerts = []
    for i in range(STAGNATION_WEEKS - 1, len(real_results)):
        window = real_results[i - STAGNATION_WEEKS + 1 : i + 1]
        max_change = max(abs(r.weight_delta_kg) for r in window)
        if max_change <= STAGNATION_THRESHOLD_KG:
            alerts.append(
                Alert(
                    type="stagnation",
                    severity="info",
                    date=window[-1].date,
                    message=(
                        f"Weight has moved less than {STAGNATION_THRESHOLD_KG} kg for "
                        f"{STAGNATION_WEEKS} consecutive weeks -- possible plateau."
                    ),
                    value=max_change,
                    threshold=STAGNATION_THRESHOLD_KG,
                )
            )
    return alerts


def _excessive_lean_loss_alerts(results: Sequence[CompositionResult]) -> List[Alert]:
    real_results = [r for r in results if r.source == "real"]
    alerts = []
    for i in range(LEAN_LOSS_WINDOW_WEEKS, len(real_results)):
        start, end = real_results[i - LEAN_LOSS_WINDOW_WEEKS], real_results[i]
        start_weight = start.fat_mass_kg + start.lean_mass_kg
        end_weight = end.fat_mass_kg + end.lean_mass_kg
        total_loss = start_weight - end_weight
        if total_loss <= 0:
            continue  # not a net loss over the window
        lean_loss = start.lean_mass_kg - end.lean_mass_kg
        share = lean_loss / total_loss
        if share > MAX_LEAN_MASS_LOSS_SHARE:
            alerts.append(
                Alert(
                    type="excessive_lean_loss",
                    severity="warning",
                    date=end.date,
                    message=(
                        f"Lean mass made up {share:.0%} of the weight lost over the "
                        f"last {LEAN_LOSS_WINDOW_WEEKS} weeks -- consider more protein "
                        "or resistance training."
                    ),
                    value=share,
                    threshold=MAX_LEAN_MASS_LOSS_SHARE,
                )
            )
    return alerts


def _deviation_alerts(results: Sequence[CompositionResult]) -> List[Alert]:
    alerts = []
    for result in results:
        if result.source != "real":
            continue
        if abs(result.weight_gap_kg) > SIGNIFICANT_DEVIATION_KG:
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
                    threshold=SIGNIFICANT_DEVIATION_KG,
                )
            )
    return alerts


def detect_alerts(results: Sequence[CompositionResult]) -> List[Alert]:
    """Run every detector over a computed series, oldest first.

    ``results`` need not be pre-sorted or pre-filtered to real rows --
    each detector orders/filters what it needs.
    """
    ordered = sorted(results, key=lambda r: r.date)
    alerts = (
        _implausible_change_alerts(ordered)
        + _stagnation_alerts(ordered)
        + _excessive_lean_loss_alerts(ordered)
        + _deviation_alerts(ordered)
    )
    return sorted(alerts, key=lambda a: a.date)
