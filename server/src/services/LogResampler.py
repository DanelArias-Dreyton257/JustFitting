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
from typing import Dict, List, Optional, Sequence, Tuple

from server.src.data.domain.BodyLog import BodyLog


def _mean_of_logged(values: Sequence[Optional[float]]) -> Optional[float]:
    """Average whatever days logged this field (minimum 1), rather than
    requiring every day in the week -- originally Phase 3.4 (Wave 2, F9)'s
    macro-averaging rule, generalized in Phase 7.4 (partial logs, see
    README) to weight/waist/neck/intake/steps too, now that any of those
    can also be missing on a given day. `None` if no day in the group
    logged it at all."""
    logged = [v for v in values if v is not None]
    return mean(logged) if logged else None


def _median_of_logged(values: Sequence[Optional[float]]) -> Optional[float]:
    """Same graceful-degradation rule as `_mean_of_logged`, but median --
    used for weight specifically (robust to a day's water/sodium swing)."""
    logged = [v for v in values if v is not None]
    return median(logged) if logged else None


def _fill_missing(
    current: Optional[float], values: Sequence[Optional[float]], *, median: bool = False
) -> Optional[float]:
    """`current` if it's already logged, otherwise the daily group's own
    graceful-degradation aggregate -- the same rule a lone daily group
    already applies to itself, just deferring to a value a weekly row
    already has instead of overwriting it."""
    if current is not None:
        return current
    return _median_of_logged(values) if median else _mean_of_logged(values)


def resample_to_weekly(logs: List[BodyLog]) -> List[BodyLog]:
    """One `BodyLog` per calendar week. Daily-tagged rows in the same ISO
    week collapse into a single representative row (median weight; mean of
    everything else; intake_is_real only if every day's intake was real).

    A weekly-tagged row is normally passed through untouched, *except* when
    exactly one such row shares its ISO week with daily-tagged rows (Phase
    7.4/7.5: a weekly manual entry -- typically just weight/waist/neck --
    coexisting with Health Connect's daily-synced steps/nutrition). In that
    one case, the weekly row is completed in place from the daily group's
    aggregate wherever the weekly row itself is missing a field, rather
    than left stranded next to a second, separately-incomplete
    representative row for the exact same week -- otherwise neither row
    alone has everything `is_computable` needs, even though the account's
    data for that week genuinely is complete once combined. Two or more
    weekly rows sharing an ISO week are never merged into a daily group --
    which of them would "own" the merge is ambiguous, so each is left
    untouched and the daily group still gets its own representative row.
    """
    weekly = [log for log in logs if log.granularity != "daily"]
    daily = [log for log in logs if log.granularity == "daily"]

    weekly_by_iso_week: Dict[Tuple[int, int], List[BodyLog]] = defaultdict(list)
    for log in weekly:
        weekly_by_iso_week[log.date.isocalendar()[:2]].append(log)

    groups: Dict[Tuple[int, int], List[BodyLog]] = defaultdict(list)
    for log in daily:
        groups[log.date.isocalendar()[:2]].append(log)

    resampled = list(weekly)
    for iso_week, group in groups.items():
        group.sort(key=lambda log: log.date)
        matching_weekly = weekly_by_iso_week.get(iso_week, [])

        if len(matching_weekly) == 1:
            weekly_log = matching_weekly[0]
            resampled.remove(weekly_log)
            resampled.append(
                replace(
                    weekly_log,
                    weight_kg=_fill_missing(
                        weekly_log.weight_kg, (log.weight_kg for log in group), median=True
                    ),
                    waist_cm=_fill_missing(weekly_log.waist_cm, (log.waist_cm for log in group)),
                    neck_cm=_fill_missing(weekly_log.neck_cm, (log.neck_cm for log in group)),
                    intake_kcal=_fill_missing(
                        weekly_log.intake_kcal, (log.intake_kcal for log in group)
                    ),
                    intake_is_real=(
                        weekly_log.intake_is_real
                        if weekly_log.intake_kcal is not None
                        else all(
                            log.intake_is_real for log in group if log.intake_kcal is not None
                        )
                    ),
                    steps=_fill_missing(weekly_log.steps, (log.steps for log in group)),
                    carbs_g=_fill_missing(weekly_log.carbs_g, (log.carbs_g for log in group)),
                    fat_g=_fill_missing(weekly_log.fat_g, (log.fat_g for log in group)),
                    protein_g=_fill_missing(
                        weekly_log.protein_g, (log.protein_g for log in group)
                    ),
                )
            )
            continue

        representative = group[-1]
        resampled.append(
            replace(
                representative,
                weight_kg=_median_of_logged(log.weight_kg for log in group),
                waist_cm=_mean_of_logged(log.waist_cm for log in group),
                neck_cm=_mean_of_logged(log.neck_cm for log in group),
                intake_kcal=_mean_of_logged(log.intake_kcal for log in group),
                # Phase 7.4 (partial logs): a day with no intake logged at
                # all doesn't get a vote either way -- `all()` over an
                # empty sequence is `True`, the same "assume real" default
                # every pre-Phase-7.4 log already had.
                intake_is_real=all(
                    log.intake_is_real for log in group if log.intake_kcal is not None
                ),
                steps=_mean_of_logged(log.steps for log in group),
                cardio_kcal=mean(log.cardio_kcal for log in group),
                carbs_g=_mean_of_logged(log.carbs_g for log in group),
                fat_g=_mean_of_logged(log.fat_g for log in group),
                protein_g=_mean_of_logged(log.protein_g for log in group),
            )
        )

    return sorted(resampled, key=lambda log: log.date)


def is_computable(log: BodyLog) -> bool:
    """Whether a (possibly resampled) row has everything
    `CompositionEngine.compute_row` needs -- see its
    `REQUIRED_FOR_COMPUTATION`/`require_complete_log_input`. Phase 7.4
    (partial logs, see README): a week can be "logged" (it has a row, or a
    resampled group of daily rows) without being computable yet, if no
    source has supplied one of these fields for any day in it."""
    return (
        log.weight_kg is not None
        and log.waist_cm is not None
        and log.neck_cm is not None
        and log.intake_kcal is not None
        and log.steps is not None
    )


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
