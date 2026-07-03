"""BMR / NEAT / TDEE / target-calories energy model (Cunningham + Mifflin-St
Jeor BMR)."""

from __future__ import annotations

from server.src.services.composition.constants import (
    NEAT_STEP_FACTOR,
    SEX_MALE,
    TEF,
)


def compute_bmr(lean_mass_kg: float) -> float:
    """Cunningham BMR -- driven by lean mass, unchanged since Phase 1."""
    return 500 + 22 * lean_mass_kg


def compute_bmr_mifflin(weight_kg: float, height_cm: float, age: int, sex: int) -> float:
    """Mifflin-St Jeor BMR (Phase 3, F4) -- driven by weight/height/age, with
    a correctly sex-specific term (`+5` male, `-161` female), unlike RFM/Navy
    above. Offered as an alternative to Cunningham for bulk accounts, whose
    lean-mass estimate is comparatively noisy early in a bulk."""
    return 10 * weight_kg + 6.25 * height_cm - 5 * age + (5 if sex == SEX_MALE else -161)


def compute_neat(
    weight_kg: float, steps: float, neat_step_factor: float = NEAT_STEP_FACTOR
) -> float:
    return neat_step_factor * weight_kg * (steps / 1000)


def compute_tdee(bmr: float, neat: float, tef: float = TEF) -> float:
    return (bmr + neat) / (1 - tef)


def compute_target_calories(
    bmr: float, neat: float, daily_deficit: float, tef: float = TEF
) -> float:
    return (bmr + neat - daily_deficit) / (1 - tef)


def compute_intake_diff(intake_kcal: float, target_calories: float) -> float:
    return intake_kcal - target_calories
