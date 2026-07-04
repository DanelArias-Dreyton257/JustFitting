"""Plain data carriers passed between composition engine modules.

These are engine-internal value objects, distinct from the persistence
domain models in data/domain and the API dto/ layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

from server.src.services.composition import constants


@dataclass(frozen=True)
class EngineConstants:
    """Per-user-overridable engine tunables (energy model + alert
    thresholds). Defaults reproduce today's fixed `constants.py` values
    exactly, so passing no override changes nothing (see Phase 1.5,
    `services/EngineSettingsManager.py`)."""

    tef: float = constants.TEF
    kcal_per_kg_fat: float = constants.KCAL_PER_KG_FAT
    neat_step_factor: float = constants.NEAT_STEP_FACTOR
    implausible_weekly_change_pct: float = constants.IMPLAUSIBLE_WEEKLY_CHANGE_PCT
    stagnation_weeks: int = constants.STAGNATION_WEEKS
    stagnation_threshold_kg: float = constants.STAGNATION_THRESHOLD_KG
    lean_loss_window_weeks: int = constants.LEAN_LOSS_WINDOW_WEEKS
    max_lean_mass_loss_share: float = constants.MAX_LEAN_MASS_LOSS_SHARE
    significant_deviation_kg: float = constants.SIGNIFICANT_DEVIATION_KG

    # Wave 2 (Phase 3) calibration constants -- see constants.py for the
    # rationale of each default.
    bmr_model: str = "cunningham"  # "cunningham" | "mifflin"
    w_rfm: float = constants.BF_WEIGHT_RFM
    w_navy: float = constants.BF_WEIGHT_NAVY
    w_deur: float = constants.BF_WEIGHT_DEURENBERG
    delta: float = constants.BF_FAT_OFFSET
    ffmi_coef: float = constants.FFMI_COEF
    lean_tissue_kcal_per_kg: float = constants.LEAN_TISSUE_KCAL_PER_KG
    fat_ratio_ideal: float = constants.FAT_RATIO_IDEAL

    # Phase 3.2 (Wave 2, F5) -- energy reconciliation.
    reconciliation_error_threshold_kcal: float = (
        constants.RECONCILIATION_ERROR_THRESHOLD_KCAL
    )

    # Phase 3.4 (Wave 2, F9) -- TEF by macronutrients.
    tef_mode: str = constants.TEF_MODE_DEFAULT  # "flat" | "macros"
    kappa_carbs: float = constants.KAPPA_CARBS
    kappa_fat: float = constants.KAPPA_FAT
    kappa_protein: float = constants.KAPPA_PROTEIN
    macro_kcal_mismatch_pct: float = constants.MACRO_KCAL_MISMATCH_PCT

    # Phase 3.4 extension -- evidence-based macro targets (g/kg body mass);
    # carbs derive as the remainder of target_calories, so there's no
    # carbs_target_g_per_kg field (see services/composition/MacroTargets.py).
    protein_target_g_per_kg: float = constants.PROTEIN_TARGET_G_PER_KG
    fat_target_g_per_kg: float = constants.FAT_TARGET_G_PER_KG
    macro_target_deviation_pct: float = constants.MACRO_TARGET_DEVIATION_PCT


DEFAULT_ENGINE_CONSTANTS = EngineConstants()


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
    cardio_kcal: float = 0.0  # EAT, Phase 3.1's F2 -- default 0 preserves Danel exactly

    # Phase 3.4 (Wave 2, F9) -- daily/weekly macro grams; all three are
    # present together or not at all (see CompositionEngine.validate_log_input).
    # `None` (the default, every pre-existing log) falls back to flat TEF.
    carbs_g: Optional[float] = None
    fat_g: Optional[float] = None
    protein_g: Optional[float] = None


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
    tef_kcal: float  # Phase 3.4, F9 -- the actual kcal figure this row used
    tef_mode: str  # "flat" | "macros" -- which formula this row actually applied

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
