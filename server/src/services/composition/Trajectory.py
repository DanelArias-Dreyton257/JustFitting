"""Goal trajectory: weekly deltas, target deficit and weeks-to-goal.

The first row in a series has no predecessor, so dW, pct and Pi are defined
as 0 there and Wobj_1 = W_1 (see docs/composition_spec.md).
"""

from __future__ import annotations

import math
from typing import Optional

from server.src.services.composition.constants import KCAL_PER_KG_FAT


def compute_weight_delta(weight_kg: float, prev_weight_kg: Optional[float]) -> float:
    if prev_weight_kg is None:
        return 0.0
    return weight_kg - prev_weight_kg


def compute_weight_delta_pct(
    weight_kg: float, prev_weight_kg: Optional[float]
) -> float:
    if prev_weight_kg is None:
        return 0.0
    return (weight_kg - prev_weight_kg) / prev_weight_kg


def compute_weight_objective(
    weight_kg: float, prev_weight_kg: Optional[float], weekly_rate: float
) -> float:
    if prev_weight_kg is None:
        return weight_kg
    return prev_weight_kg * (1 + weekly_rate)


def compute_weight_gap(weight_kg: float, weight_objective_kg: float) -> float:
    return weight_kg - weight_objective_kg


def compute_weight_to_shed(
    prev_weight_kg: Optional[float], weight_objective_kg: float
) -> float:
    if prev_weight_kg is None:
        return 0.0
    return prev_weight_kg - weight_objective_kg


def compute_weekly_deficit(
    weight_to_shed_kg: float, kcal_per_kg_fat: float = KCAL_PER_KG_FAT
) -> float:
    return weight_to_shed_kg * kcal_per_kg_fat


def compute_daily_deficit(weekly_deficit_kcal: float) -> float:
    return weekly_deficit_kcal / 7


def compute_final_weight(lean_mass_kg: float, target_bf: float) -> float:
    return lean_mass_kg / (1 - target_bf)


#: Below this magnitude, `weekly_rate` is treated as exactly zero -- same
#: tolerance and reasoning as IncrementAnalytics.py's own zero-rate guard.
_ZERO_RATE_EPSILON = 1e-9


def compute_weeks_to_goal(
    weight_kg: float, final_weight_kg: float, weekly_rate: float
) -> float:
    if abs(weekly_rate) < _ZERO_RATE_EPSILON:
        # ln(1 - 0) = 0 would otherwise divide by zero -- a 0% weekly rate
        # ("no change yet", Phase 5.2's brand-new-account default) has no
        # trajectory to project against. 0.0 is the same "no meaningful
        # figure" sentinel already produced when weight_kg == final_weight_kg
        # (the numerator is 0), which every consumer already renders as "--".
        return 0.0
    return math.log(weight_kg / final_weight_kg) / math.log(1 - weekly_rate)
