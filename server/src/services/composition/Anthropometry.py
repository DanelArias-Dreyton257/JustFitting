"""Age, BMI and FFMI — the first stage of the composition engine.

See docs/composition_spec.md for the formulas this module implements.
"""

from __future__ import annotations

from datetime import date

from server.src.services.composition.constants import (
    DAYS_PER_YEAR,
    FFMI_COEF,
    FFMI_HEIGHT_REF_M,
)


def compute_age(as_of: date, birthdate: date) -> int:
    if as_of < birthdate:
        raise ValueError("as_of date cannot precede birthdate")
    return int((as_of - birthdate).days // DAYS_PER_YEAR)


def compute_bmi(weight_kg: float, height_cm: float) -> float:
    _require_positive(weight_kg=weight_kg, height_cm=height_cm)
    height_m = height_cm / 100
    return round(weight_kg / (height_m**2), 2)


def compute_ffmi(lean_mass_kg: float, height_cm: float) -> float:
    _require_positive(lean_mass_kg=lean_mass_kg, height_cm=height_cm)
    height_m = height_cm / 100
    return lean_mass_kg / (height_m**2)


def compute_ffmi_adjusted(
    ffmi: float, height_cm: float, ffmi_coef: float = FFMI_COEF
) -> float:
    height_m = height_cm / 100
    return ffmi + ffmi_coef * (FFMI_HEIGHT_REF_M - height_m)


def _require_positive(**values: float) -> None:
    for name, value in values.items():
        if value is None or value <= 0:
            raise ValueError(f"{name} must be positive, got {value!r}")
