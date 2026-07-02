"""Forecasts future weekly rows from a real-log history.

Weight/waist/neck follow an OLS linear trend (the spreadsheet TREND()
equivalent); steps are held constant; intake is assumed to equal the
previous row's recommended target calories and is marked as not real, so
adherence metrics must only be computed over ``intake_is_real=True`` rows.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import List, Literal, Sequence, Tuple

from server.src.services.composition import CompositionEngine
from server.src.services.composition.constants import DAYS_PER_WEEK
from server.src.services.composition.models import (
    CompositionResult,
    LogInput,
    ProfileParams,
)

BaseRegression = Literal["real_only", "real_and_projected"]


def _ols(xs: Sequence[float], ys: Sequence[float]) -> Tuple[float, float]:
    n = len(xs)
    if n < 2:
        raise ValueError("at least two points are required to fit a trend")
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    denominator = sum((x - mean_x) ** 2 for x in xs)
    if denominator == 0:
        return 0.0, mean_y
    slope = numerator / denominator
    intercept = mean_y - slope * mean_x
    return slope, intercept


def _forecast(history: Sequence[LogInput], attr: str, target_date: date) -> float:
    base_date = history[0].date
    xs = [(log.date - base_date).days for log in history]
    ys = [getattr(log, attr) for log in history]
    slope, intercept = _ols(xs, ys)
    x_target = (target_date - base_date).days
    return slope * x_target + intercept


def project_series(
    profile: ProfileParams,
    real_logs: Sequence[LogInput],
    weeks: int,
    base_regression: BaseRegression = "real_only",
) -> List[CompositionResult]:
    """Forecast ``weeks`` future weekly rows beyond the last real log."""
    if weeks <= 0:
        return []
    if len(real_logs) < 2:
        raise ValueError("at least two real logs are required to project a trend")

    ordered_real = sorted(real_logs, key=lambda log: log.date)
    real_results = CompositionEngine.compute_series(profile, ordered_real)

    history: List[LogInput] = list(ordered_real)
    last_steps = ordered_real[-1].steps
    prev_weight_kg = ordered_real[-1].weight_kg
    prev_target_calories = real_results[-1].target_calories

    projected_results: List[CompositionResult] = []
    cursor_date = ordered_real[-1].date

    for _ in range(weeks):
        cursor_date = cursor_date + timedelta(days=DAYS_PER_WEEK)
        regression_source = (
            history if base_regression == "real_and_projected" else ordered_real
        )
        forecast_weight = _forecast(regression_source, "weight_kg", cursor_date)
        forecast_waist = _forecast(regression_source, "waist_cm", cursor_date)
        forecast_neck = _forecast(regression_source, "neck_cm", cursor_date)

        projected_log = LogInput(
            date=cursor_date,
            weight_kg=forecast_weight,
            waist_cm=forecast_waist,
            neck_cm=forecast_neck,
            intake_kcal=prev_target_calories,
            steps=last_steps,
            intake_is_real=False,
        )

        result = CompositionEngine.compute_row(profile, projected_log, prev_weight_kg)
        projected_results.append(result)

        history.append(projected_log)
        prev_weight_kg = projected_log.weight_kg
        prev_target_calories = result.target_calories

    return projected_results
