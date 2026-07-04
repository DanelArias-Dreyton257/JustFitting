"""Body-fat estimators and the resulting mass partition.

Implements RFM, the US Navy method and the Deurenberg formula, then
combines them into the headline weighted body-fat percentage.
"""

from __future__ import annotations

import math

from server.src.services.composition.constants import (
    BF_FAT_OFFSET,
    BF_WEIGHT_DEURENBERG,
    BF_WEIGHT_NAVY,
    BF_WEIGHT_RFM,
)


def compute_rfm(height_cm: float, waist_cm: float) -> float:
    return (64 - 20 * (height_cm / waist_cm)) / 100


def compute_navy(height_cm: float, waist_cm: float, neck_cm: float) -> float:
    if waist_cm <= neck_cm:
        raise ValueError("waist_cm must be greater than neck_cm for the Navy method")
    denominator = (
        1.0324
        - 0.19077 * math.log10(waist_cm - neck_cm)
        + 0.15456 * math.log10(height_cm)
    )
    return (495 / denominator - 450) / 100


def compute_deurenberg(bmi: float, age: int, sex: int) -> float:
    return (1.2 * bmi + 0.23 * age - 10.8 * sex - 5.4) / 100


def compute_body_fat(
    rfm: float,
    navy: float,
    deurenberg: float,
    w_rfm: float = BF_WEIGHT_RFM,
    w_navy: float = BF_WEIGHT_NAVY,
    w_deur: float = BF_WEIGHT_DEURENBERG,
    delta: float = BF_FAT_OFFSET,
) -> float:
    """Weighted mean of the three body-fat estimators, plus an optional
    per-account offset (`delta`, Phase 3/Wave 2's F8) -- defaults
    reproduce today's fixed weights and a zero offset exactly."""
    return w_rfm * rfm + w_navy * navy + w_deur * deurenberg + delta


def compute_fat_mass(weight_kg: float, body_fat: float) -> float:
    return round(weight_kg * body_fat, 2)


def compute_lean_mass(weight_kg: float, body_fat: float) -> float:
    return round(weight_kg * (1 - body_fat), 2)


def compute_above_target(body_fat: float, target_bf: float) -> float:
    return body_fat - target_bf
