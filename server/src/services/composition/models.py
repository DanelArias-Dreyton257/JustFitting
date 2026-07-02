"""Plain data carriers passed between composition engine modules.

These are engine-internal value objects, distinct from the persistence
domain models in data/domain and the API dto/ layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class ProfileParams:
    """Static, per-user inputs the engine needs on every computation."""

    height_cm: float
    sex: int  # 1 = male, 0 = female
    birthdate: date
    target_bf: float  # tau, fraction e.g. 0.15
    weekly_rate: float  # r, fraction/week e.g. -0.005


@dataclass(frozen=True)
class LogInput:
    """One weekly measurement row (real or projected)."""

    date: date
    weight_kg: float
    waist_cm: float
    neck_cm: float
    intake_kcal: float
    steps: float
    intake_is_real: bool = True


@dataclass(frozen=True)
class CompositionResult:
    """Every derived metric for a single weekly row, in spec order."""

    date: date

    # Anthropometry
    age: int
    bmi: float
    ffmi: float
    ffmi_adj: float

    # Body-fat estimators (fractions)
    rfm: float
    navy: float
    deurenberg: float
    body_fat: float

    # Mass partition & distance to target
    fat_mass_kg: float
    lean_mass_kg: float
    above_target: float  # AJ, fraction

    # Energy model
    bmr: float
    neat: float
    tdee: float
    target_calories: float
    intake_diff: float

    # Goal & trajectory
    weight_delta_kg: float  # dW
    weight_delta_pct: float  # pct
    weight_objective_kg: float  # Wobj
    weight_gap_kg: float  # K
    weight_to_shed_kg: float  # Pi
    weekly_deficit_kcal: float
    daily_deficit_kcal: float
    final_weight_kg: float  # Wfinal
    weeks_to_goal: float

    source: str = "real"  # "real" | "projected"
