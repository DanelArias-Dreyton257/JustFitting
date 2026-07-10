"""Forecasts future weekly rows from a real-log history.

Weight follows a linear trend fit -- either plain OLS (the spreadsheet
TREND() equivalent) or, since Phase 1.6, a recency-weighted OLS
(``trend_model="weighted_ols"``) that leans more on recent weeks; steps
default to held-constant but can follow the same trend fit instead
(``activity_model="trend"``, Phase 1.5); intake is assumed to equal the
previous row's recommended target calories and is marked as not real, so
adherence metrics must only be computed over ``intake_is_real=True`` rows.

Phase 9.1 (body composition logging separation, see README): waist/neck no
longer live on the weekly log history at all -- their trend-fit source
moves to the sparser, irregularly-dated ``body_measurements`` history
(``measurement_history``), falling back to holding the last resolved
waist/neck constant whenever fewer than two measurements exist to fit a
trend against (the same "static until next update" idea, just extended
into the future since there's no future update to anchor to yet).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import List, Literal, Optional, Sequence, Tuple

from server.src.services.composition import CompositionEngine
from server.src.services.composition.constants import DAYS_PER_WEEK, WEIGHTED_TREND_DECAY
from server.src.services.composition.models import (
    CompositionResult,
    EngineConstants,
    LogInput,
    ProfileParams,
)


@dataclass(frozen=True)
class MeasurementPoint:
    """One dated waist/neck reading -- shaped just enough like a
    `BodyMeasurement` (`.date`/`.waist_cm`/`.neck_cm`) for `_forecast` to fit
    a trend against, real or forecasted."""

    date: date
    waist_cm: float
    neck_cm: float

BaseRegression = Literal["real_only", "real_and_projected"]
ActivityModel = Literal["constant", "trend"]
TrendModel = Literal["ols", "weighted_ols"]


def _weighted_ols(
    xs: Sequence[float], ys: Sequence[float], weights: Sequence[float]
) -> Tuple[float, float]:
    n = len(xs)
    if n < 2:
        raise ValueError("at least two points are required to fit a trend")
    total_weight = sum(weights)
    mean_x = sum(w * x for w, x in zip(weights, xs)) / total_weight
    mean_y = sum(w * y for w, y in zip(weights, ys)) / total_weight
    numerator = sum(
        w * (x - mean_x) * (y - mean_y) for w, x, y in zip(weights, xs, ys)
    )
    denominator = sum(w * (x - mean_x) ** 2 for w, x in zip(weights, xs))
    if denominator == 0:
        return 0.0, mean_y
    slope = numerator / denominator
    intercept = mean_y - slope * mean_x
    return slope, intercept


def _ols(xs: Sequence[float], ys: Sequence[float]) -> Tuple[float, float]:
    """Plain OLS -- equivalent to ``_weighted_ols`` with uniform weights."""
    return _weighted_ols(xs, ys, [1.0] * len(xs))


def _recency_weights(xs: Sequence[float]) -> List[float]:
    most_recent = max(xs)
    return [
        WEIGHTED_TREND_DECAY ** ((most_recent - x) / DAYS_PER_WEEK) for x in xs
    ]


def _forecast(
    history: Sequence[LogInput],
    attr: str,
    target_date: date,
    trend_model: TrendModel = "ols",
) -> float:
    base_date = history[0].date
    xs = [(log.date - base_date).days for log in history]
    ys = [getattr(log, attr) for log in history]
    if trend_model == "weighted_ols":
        slope, intercept = _weighted_ols(xs, ys, _recency_weights(xs))
    else:
        slope, intercept = _ols(xs, ys)
    x_target = (target_date - base_date).days
    return slope * x_target + intercept


def project_series(
    profile: ProfileParams,
    real_logs: Sequence[LogInput],
    weeks: int,
    base_regression: BaseRegression = "real_only",
    activity_model: ActivityModel = "constant",
    engine_constants: Optional[EngineConstants] = None,
    trend_model: TrendModel = "ols",
    measurement_history: Optional[Sequence[MeasurementPoint]] = None,
) -> List[CompositionResult]:
    """Forecast ``weeks`` future weekly rows beyond the last real log."""
    return [
        result
        for _, result in project_series_with_inputs(
            profile,
            real_logs,
            weeks,
            base_regression,
            activity_model,
            engine_constants,
            trend_model,
            measurement_history,
        )
    ]


def project_series_with_inputs(
    profile: ProfileParams,
    real_logs: Sequence[LogInput],
    weeks: int,
    base_regression: BaseRegression = "real_only",
    activity_model: ActivityModel = "constant",
    engine_constants: Optional[EngineConstants] = None,
    trend_model: TrendModel = "ols",
    measurement_history: Optional[Sequence[MeasurementPoint]] = None,
) -> List[Tuple[LogInput, CompositionResult]]:
    """Same as ``project_series``, but also returns each forecasted row's raw
    ``LogInput`` (estimated weight/waist/neck) alongside its ``CompositionResult``
    -- needed to persist a saved forecast run (see ``ProjectionService``),
    since the derived metrics alone don't carry the raw estimates back out.

    ``activity_model`` controls the forecast's steps assumption: ``"constant"``
    (default) carries the last real log's steps forward unchanged;
    ``"trend"`` fits the same trend model used for weight.

    ``trend_model`` controls how the linear trend itself is fit: ``"ols"``
    (default) is plain least-squares; ``"weighted_ols"`` (Phase 1.6) weights
    more recent weeks more heavily (see ``_recency_weights``).

    ``measurement_history`` (Phase 9.1) is the account's real
    ``body_measurements`` history, sorted or not -- waist/neck are trend-fit
    against it directly (a strictly sparser, irregularly-dated series) when
    it has at least two points; otherwise the last resolved waist/neck on
    ``real_logs`` is held constant for every forecasted week, since there's
    nothing to fit a trend against yet.
    """
    if weeks <= 0:
        return []
    if len(real_logs) < 2:
        raise ValueError("at least two real logs are required to project a trend")

    ordered_real = sorted(real_logs, key=lambda log: log.date)
    real_results = CompositionEngine.compute_series(profile, ordered_real, engine_constants)

    history: List[LogInput] = list(ordered_real)
    last_steps = ordered_real[-1].steps
    prev_weight_kg = ordered_real[-1].weight_kg
    prev_target_calories = real_results[-1].target_calories

    measurement_pts: List[MeasurementPoint] = sorted(
        (
            MeasurementPoint(m.date, m.waist_cm, m.neck_cm)
            for m in (measurement_history or [])
            if m.waist_cm is not None and m.neck_cm is not None
        ),
        key=lambda point: point.date,
    )
    last_waist_cm = ordered_real[-1].waist_cm
    last_neck_cm = ordered_real[-1].neck_cm

    projected_pairs: List[Tuple[LogInput, CompositionResult]] = []
    cursor_date = ordered_real[-1].date

    for _ in range(weeks):
        cursor_date = cursor_date + timedelta(days=DAYS_PER_WEEK)
        regression_source = (
            history if base_regression == "real_and_projected" else ordered_real
        )
        forecast_weight = _forecast(regression_source, "weight_kg", cursor_date, trend_model)
        if len(measurement_pts) >= 2:
            forecast_waist = _forecast(measurement_pts, "waist_cm", cursor_date, trend_model)
            forecast_neck = _forecast(measurement_pts, "neck_cm", cursor_date, trend_model)
        else:
            forecast_waist = last_waist_cm
            forecast_neck = last_neck_cm
        if activity_model == "trend":
            forecast_steps = max(
                0.0, _forecast(regression_source, "steps", cursor_date, trend_model)
            )
        else:
            forecast_steps = last_steps

        projected_log = LogInput(
            date=cursor_date,
            weight_kg=forecast_weight,
            waist_cm=forecast_waist,
            neck_cm=forecast_neck,
            intake_kcal=prev_target_calories,
            steps=forecast_steps,
            intake_is_real=False,
        )

        result = CompositionEngine.compute_row(
            profile, projected_log, prev_weight_kg, engine_constants
        )
        projected_pairs.append((projected_log, result))

        history.append(projected_log)
        if base_regression == "real_and_projected" and len(measurement_pts) >= 2:
            measurement_pts.append(
                MeasurementPoint(cursor_date, forecast_waist, forecast_neck)
            )
        prev_weight_kg = projected_log.weight_kg
        prev_target_calories = result.target_calories

    return projected_pairs
