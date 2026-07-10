"""Same-day estimate for the Dashboard's "Today" section (Phase 10.2, see
README). Today's own `BodyLog` row is essentially never `is_computable`
(no full week's worth of anything, often not even logged yet at all) --
so its NEAT/TEF/EAT figures can't come from a persisted `compute_row`
result. This generalizes Phase 9.1's "static until next update" idea from
perimeters to lean mass/BMR: NEAT is recomputed from today's real steps
against the most recently *computed* week's own total weight (held
static, the same "hold the last known value" pattern), TEF from today's
real macros when logged (else the flat estimate, using that same held BMR
plus the NEAT/EAT just computed), and EAT straight from today's real
`cardio_kcal`. Like `GainQuality.py`/`EnergyReconciliation.py`, a pure
read-side view over already-computed data -- never persisted to
`metrics_snapshots`, no `ENGINE_VERSION` implication, the same "computed
but not cached" precedent `GET /api/plan/preview` already established.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as date_type
from typing import Optional, Protocol

from server.src.services.composition import Tef
from server.src.services.composition.models import (
    DEFAULT_ENGINE_CONSTANTS,
    CompositionResult,
    EngineConstants,
)


class _LogLike(Protocol):
    """The `BodyLog` fields this module reads -- today's own (possibly
    still-partial) row."""

    weight_kg: Optional[float]
    intake_kcal: Optional[float]
    steps: Optional[float]
    cardio_kcal: float
    carbs_g: Optional[float]
    fat_g: Optional[float]
    protein_g: Optional[float]


@dataclass(frozen=True)
class TodayEstimateRow:
    date: date_type
    #: Inferred, not stored (README's Phase 10.2 plan): true whenever
    #: there's no row for today yet, or today's row isn't computable --
    #: stops being "current" automatically once the day rolls over or the
    #: row is completed, no lifecycle to manage.
    is_current: bool
    steps: Optional[float]
    intake_kcal: Optional[float]
    cardio_kcal: Optional[float]
    target_calories: Optional[float]  # held from the most recent computed week
    kcal_to_target: Optional[float]  # target_calories - intake_kcal
    neat_kcal: Optional[float]
    tef_kcal: Optional[float]
    tef_mode: Optional[str]  # "flat" | "macros" -- which one this estimate used
    eat_kcal: Optional[float]
    steps_goal: Optional[float] = None
    cardio_kcal_goal: Optional[float] = None
    steps_left: Optional[float] = None
    cardio_left: Optional[float] = None


def compute_today_estimate(
    today: date_type,
    today_log: Optional[_LogLike],
    latest_result: Optional[CompositionResult],
    engine_constants: Optional[EngineConstants] = None,
    steps_goal: Optional[float] = None,
    cardio_kcal_goal: Optional[float] = None,
) -> TodayEstimateRow:
    """``latest_result`` is the most recent *computed* week (from
    `MetricsSeriesService.compute_series_for_user`'s own output), `None`
    for an account with no computable week yet -- in which case every
    estimate figure below stays `None` too (nothing to hold static)."""
    ec = engine_constants or DEFAULT_ENGINE_CONSTANTS

    steps = today_log.steps if today_log else None
    intake_kcal = today_log.intake_kcal if today_log else None
    cardio_kcal = today_log.cardio_kcal if today_log else None

    is_current = today_log is None or not (
        today_log.weight_kg is not None
        and today_log.intake_kcal is not None
        and today_log.steps is not None
    )

    held_weight_kg = (
        latest_result.fat_mass_kg + latest_result.lean_mass_kg if latest_result else None
    )
    held_bmr = latest_result.bmr if latest_result else None
    target_calories = latest_result.target_calories if latest_result else None

    neat_kcal = None
    if steps is not None and held_weight_kg is not None:
        neat_kcal = ec.neat_step_factor * held_weight_kg * (steps / 1000)

    has_macros = (
        today_log is not None
        and today_log.carbs_g is not None
        and today_log.fat_g is not None
        and today_log.protein_g is not None
    )
    tef_kcal: Optional[float] = None
    tef_mode: Optional[str] = None
    if ec.tef_mode == "macros" and has_macros:
        tef_kcal = Tef.compute_tef_kcal(
            today_log.carbs_g,
            today_log.fat_g,
            today_log.protein_g,
            ec.kappa_carbs,
            ec.kappa_fat,
            ec.kappa_protein,
        )
        tef_mode = "macros"
    elif neat_kcal is not None and held_bmr is not None:
        eat_for_tef = cardio_kcal if cardio_kcal is not None else 0.0
        tef_kcal = ec.tef * (held_bmr + neat_kcal + eat_for_tef) / (1 - ec.tef)
        tef_mode = "flat"

    kcal_to_target = (
        target_calories - intake_kcal
        if target_calories is not None and intake_kcal is not None
        else None
    )

    steps_left = steps_goal - steps if steps_goal is not None and steps is not None else None
    cardio_left = (
        cardio_kcal_goal - cardio_kcal
        if cardio_kcal_goal is not None and cardio_kcal is not None
        else None
    )

    return TodayEstimateRow(
        date=today,
        is_current=is_current,
        steps=steps,
        intake_kcal=intake_kcal,
        cardio_kcal=cardio_kcal,
        target_calories=target_calories,
        kcal_to_target=kcal_to_target,
        neat_kcal=neat_kcal,
        tef_kcal=tef_kcal,
        tef_mode=tef_mode,
        eat_kcal=cardio_kcal,
        steps_goal=steps_goal,
        cardio_kcal_goal=cardio_kcal_goal,
        steps_left=steps_left,
        cardio_left=cardio_left,
    )
