"""Orchestrates the composition engine over a chronological series of logs.

Compute order (no circular references): inputs -> age, BMI -> RFM/Navy/
Deurenberg -> BF -> Fat/Lean -> (FFMI, BMR, Wfinal) -> Wobj -> Pi ->
WeeklyDeficit -> DailyDeficit -> TDEE, TargetCal -> IntakeDiff.

This ordering is versioned: bump ENGINE_VERSION whenever it, or a formula
it depends on, changes in a way that would alter previously-computed rows.
"""

from __future__ import annotations

import warnings
from typing import List, Optional, Sequence

from server.src.services.composition import (
    Anthropometry,
    BodyFat,
    EnergyModel,
    Trajectory,
    constants,
)
from server.src.services.composition.models import (
    DEFAULT_ENGINE_CONSTANTS,
    CompositionResult,
    EngineConstants,
    LogInput,
    ProfileParams,
)

ENGINE_VERSION = 1

#: A week-over-week weight swing beyond this fraction of body weight is
#: implausible for a single week and gets flagged (not blocked). Kept as a
#: module attribute for backward compatibility (`Alerts.py` reads it);
#: overridable per-user via `EngineConstants.implausible_weekly_change_pct`.
IMPLAUSIBLE_WEEKLY_CHANGE_PCT = constants.IMPLAUSIBLE_WEEKLY_CHANGE_PCT


def validate_log_input(log: LogInput) -> None:
    """Reject non-positive measurements and an impossible waist/neck pair.

    Shared by the engine (before computing a row) and the service layer
    (before persisting a log), so both reject bad input the same way.
    """
    positive_fields = {
        "weight_kg": log.weight_kg,
        "waist_cm": log.waist_cm,
        "neck_cm": log.neck_cm,
        "intake_kcal": log.intake_kcal,
        "steps": log.steps,
    }
    for name, value in positive_fields.items():
        if value is None or value <= 0:
            raise ValueError(f"{name} must be positive, got {value!r}")
    if log.waist_cm <= log.neck_cm:
        raise ValueError("waist_cm must be greater than neck_cm")


def compute_row(
    profile: ProfileParams,
    log: LogInput,
    prev_weight_kg: Optional[float] = None,
    engine_constants: Optional[EngineConstants] = None,
) -> CompositionResult:
    """Compute every derived metric for a single weekly row.

    ``prev_weight_kg`` is the raw weight of the previous chronological row
    (``None`` for the first row in a series), which drives the base cases
    for dW, pct, Wobj and Pi. ``engine_constants`` overrides the energy
    model's fixed constants (TEF, kcal/kg fat, NEAT step factor, implausible
    -change threshold); defaults to today's `constants.py` values.
    """
    validate_log_input(log)
    ec = engine_constants or DEFAULT_ENGINE_CONSTANTS

    if prev_weight_kg is not None:
        pct = (log.weight_kg - prev_weight_kg) / prev_weight_kg
        if abs(pct) > ec.implausible_weekly_change_pct:
            warnings.warn(
                f"Implausible weekly weight change of {pct:.1%} on {log.date}",
                stacklevel=2,
            )

    age = Anthropometry.compute_age(log.date, profile.birthdate)
    bmi = Anthropometry.compute_bmi(log.weight_kg, profile.height_cm)

    rfm = BodyFat.compute_rfm(profile.height_cm, log.waist_cm)
    navy = BodyFat.compute_navy(profile.height_cm, log.waist_cm, log.neck_cm)
    deurenberg = BodyFat.compute_deurenberg(bmi, age, profile.sex)
    body_fat = BodyFat.compute_body_fat(rfm, navy, deurenberg)

    fat_mass_kg = BodyFat.compute_fat_mass(log.weight_kg, body_fat)
    lean_mass_kg = BodyFat.compute_lean_mass(log.weight_kg, body_fat)
    above_target = BodyFat.compute_above_target(body_fat, profile.target_bf)

    ffmi = Anthropometry.compute_ffmi(lean_mass_kg, profile.height_cm)
    ffmi_adj = Anthropometry.compute_ffmi_adjusted(ffmi, profile.height_cm)
    final_weight_kg = Trajectory.compute_final_weight(lean_mass_kg, profile.target_bf)
    bmr = EnergyModel.compute_bmr(lean_mass_kg)

    weight_delta_kg = Trajectory.compute_weight_delta(log.weight_kg, prev_weight_kg)
    weight_delta_pct = Trajectory.compute_weight_delta_pct(
        log.weight_kg, prev_weight_kg
    )
    weight_objective_kg = Trajectory.compute_weight_objective(
        log.weight_kg, prev_weight_kg, profile.weekly_rate
    )
    weight_gap_kg = Trajectory.compute_weight_gap(log.weight_kg, weight_objective_kg)
    weight_to_shed_kg = Trajectory.compute_weight_to_shed(
        prev_weight_kg, weight_objective_kg
    )
    weekly_deficit_kcal = Trajectory.compute_weekly_deficit(
        weight_to_shed_kg, ec.kcal_per_kg_fat
    )
    daily_deficit_kcal = Trajectory.compute_daily_deficit(weekly_deficit_kcal)
    weeks_to_goal = Trajectory.compute_weeks_to_goal(
        log.weight_kg, final_weight_kg, profile.weekly_rate
    )

    neat = EnergyModel.compute_neat(log.weight_kg, log.steps, ec.neat_step_factor)
    tdee = EnergyModel.compute_tdee(bmr, neat, ec.tef)
    target_calories = EnergyModel.compute_target_calories(
        bmr, neat, daily_deficit_kcal, ec.tef
    )
    intake_diff = EnergyModel.compute_intake_diff(log.intake_kcal, target_calories)

    return CompositionResult(
        date=log.date,
        age=age,
        bmi=bmi,
        ffmi=ffmi,
        ffmi_adj=ffmi_adj,
        rfm=rfm,
        navy=navy,
        deurenberg=deurenberg,
        body_fat=body_fat,
        fat_mass_kg=fat_mass_kg,
        lean_mass_kg=lean_mass_kg,
        above_target=above_target,
        bmr=bmr,
        neat=neat,
        tdee=tdee,
        target_calories=target_calories,
        intake_diff=intake_diff,
        weight_delta_kg=weight_delta_kg,
        weight_delta_pct=weight_delta_pct,
        weight_objective_kg=weight_objective_kg,
        weight_gap_kg=weight_gap_kg,
        weight_to_shed_kg=weight_to_shed_kg,
        weekly_deficit_kcal=weekly_deficit_kcal,
        daily_deficit_kcal=daily_deficit_kcal,
        final_weight_kg=final_weight_kg,
        weeks_to_goal=weeks_to_goal,
        source="real" if log.intake_is_real else "projected",
    )


def compute_series(
    profile: ProfileParams,
    logs: Sequence[LogInput],
    engine_constants: Optional[EngineConstants] = None,
) -> List[CompositionResult]:
    """Compute derived metrics for a chronological series of weekly logs."""
    ordered = sorted(logs, key=lambda log: log.date)
    results: List[CompositionResult] = []
    prev_weight_kg: Optional[float] = None
    for log in ordered:
        results.append(compute_row(profile, log, prev_weight_kg, engine_constants))
        prev_weight_kg = log.weight_kg
    return results
