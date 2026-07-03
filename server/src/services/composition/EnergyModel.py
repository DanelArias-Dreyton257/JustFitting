"""BMR / NEAT / TDEE / target-calories energy model (Cunningham BMR)."""

from __future__ import annotations

from server.src.services.composition.constants import NEAT_STEP_FACTOR, TEF


def compute_bmr(lean_mass_kg: float) -> float:
    return 500 + 22 * lean_mass_kg


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
