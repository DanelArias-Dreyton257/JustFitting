"""BMR / NEAT / TDEE / target-calories energy model (Cunningham BMR)."""

from __future__ import annotations

from server.src.services.composition.constants import TEF


def compute_bmr(lean_mass_kg: float) -> float:
    return 500 + 22 * lean_mass_kg


def compute_neat(weight_kg: float, steps: float) -> float:
    return 0.5 * weight_kg * (steps / 1000)


def compute_tdee(bmr: float, neat: float) -> float:
    return (bmr + neat) / (1 - TEF)


def compute_target_calories(bmr: float, neat: float, daily_deficit: float) -> float:
    return (bmr + neat - daily_deficit) / (1 - TEF)


def compute_intake_diff(intake_kcal: float, target_calories: float) -> float:
    return intake_kcal - target_calories
