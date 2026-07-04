"""Resolves a mixed daily/weekly `BodyLog` history into the one-row-per-week
shape `CompositionEngine` needs (F6, docs/composition_spec.md), and the
symmetric daily-view expansion of a weekly log across the days it covers.

Only rows tagged ``granularity="daily"`` are ever grouped: a ``"weekly"``
row (the default, and every log that existed before this feature) always
passes straight through as its own week, unchanged, regardless of what
weekday it falls on -- grouping by calendar week regardless of tag risks
merging two legitimately distinct weekly logs that happen to land in the
same ISO week for an account that doesn't log on a fixed weekday.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import date, timedelta
from statistics import mean, median
from typing import Dict, List, Tuple

from server.src.data.domain.BodyLog import BodyLog


def resample_to_weekly(logs: List[BodyLog]) -> List[BodyLog]:
    """One `BodyLog` per calendar week. Weekly-tagged rows pass through
    untouched; daily-tagged rows in the same ISO week collapse into a
    single representative row (median weight; mean of everything else;
    intake_is_real only if every day's intake was real)."""
    weekly = [log for log in logs if log.granularity != "daily"]
    daily = [log for log in logs if log.granularity == "daily"]

    groups: Dict[Tuple[int, int], List[BodyLog]] = defaultdict(list)
    for log in daily:
        groups[log.date.isocalendar()[:2]].append(log)

    resampled = list(weekly)
    for group in groups.values():
        group.sort(key=lambda log: log.date)
        representative = group[-1]
        resampled.append(
            replace(
                representative,
                weight_kg=median(log.weight_kg for log in group),
                waist_cm=mean(log.waist_cm for log in group),
                neck_cm=mean(log.neck_cm for log in group),
                intake_kcal=mean(log.intake_kcal for log in group),
                intake_is_real=all(log.intake_is_real for log in group),
                steps=mean(log.steps for log in group),
                cardio_kcal=mean(log.cardio_kcal for log in group),
            )
        )

    return sorted(resampled, key=lambda log: log.date)


@dataclass(frozen=True)
class DailyPoint:
    """A single day's weight/steps/cardio, for a future per-day display."""

    day: date
    weight_kg: float
    steps: float
    cardio_kcal: float
    source_log_id: int


def daily_view(logs: List[BodyLog]) -> List[DailyPoint]:
    """Symmetric direction: a weekly log's values are copy-pasted across
    every day since the previous log (mirrors Projection.py's
    activity_model="constant" carry-forward, just applied backward in
    time); a daily log already represents one specific day and is emitted
    as-is, never expanded."""
    ordered = sorted(logs, key=lambda log: log.date)
    points: List[DailyPoint] = []
    previous_date: date | None = None

    for log in ordered:
        if log.granularity == "daily":
            points.append(
                DailyPoint(
                    day=log.date,
                    weight_kg=log.weight_kg,
                    steps=log.steps,
                    cardio_kcal=log.cardio_kcal,
                    source_log_id=log.log_id,
                )
            )
        else:
            start = (previous_date + timedelta(days=1)) if previous_date else log.date
            day = start
            while day <= log.date:
                points.append(
                    DailyPoint(
                        day=day,
                        weight_kg=log.weight_kg,
                        steps=log.steps,
                        cardio_kcal=log.cardio_kcal,
                        source_log_id=log.log_id,
                    )
                )
                day += timedelta(days=1)
        previous_date = log.date

    return points
