"""Real-increment analytics (Phase 3.2, F7): the actual week-over-week
weight increment against the goal rate, a running mean of it, and the
normalized deviation from the goal.

`IncrReal_i` is algebraically identical to the already-computed
`CompositionResult.weight_delta_pct` -- see docs/composition_spec.md's F7
section -- so this adds no new base computation, only two aggregate/derived
views over an existing field, mirroring `GainQuality.py`/`Alerts.py`'s
"pure read-side view" pattern (no `ENGINE_VERSION` bump).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as date_type
from typing import List, Optional, Sequence

from server.src.services.composition.models import CompositionResult

#: Below this magnitude a goal rate is treated as zero -- guards against a
#: division by (near-)zero producing a huge, meaningless deviation instead
#: of the intended `None` (undefined), same "guard, don't divide" intent as
#: GainQuality._safe_ratio.
_ZERO_EPSILON = 1e-9


@dataclass(frozen=True)
class IncrementAnalyticsRow:
    """One real week's actual increment vs. the goal rate `rho`, plus the
    running mean of actual increments up to and including this week."""

    date: date_type
    incr_real_pct: float
    incr_real_mean_pct: float
    deviation_pct: Optional[float]  # Desv_i; None when weekly_rate == 0


def compute_increment_analytics(
    results: Sequence[CompositionResult],
    weekly_rate: float,
) -> List[IncrementAnalyticsRow]:
    """Walks the real (non-projected) rows of a date-sorted series, skipping
    the first -- its `weight_delta_pct` is the base-case `0.0`, not a
    genuine week-over-week measurement (same exclusion `Alerts.py`'s
    lean-loss/stagnation windows make over real rows)."""
    real_results = [r for r in sorted(results, key=lambda r: r.date) if r.source == "real"]

    rows: List[IncrementAnalyticsRow] = []
    running_sum = 0.0
    running_count = 0
    for i, result in enumerate(real_results):
        if i == 0:
            continue  # base case: no previous real week to diff against
        incr = result.weight_delta_pct
        running_sum += incr
        running_count += 1
        mean_incr = running_sum / running_count
        deviation = (
            (weekly_rate - incr) / weekly_rate
            if abs(weekly_rate) >= _ZERO_EPSILON
            else None
        )
        rows.append(
            IncrementAnalyticsRow(
                date=result.date,
                incr_real_pct=incr,
                incr_real_mean_pct=mean_incr,
                deviation_pct=deviation,
            )
        )

    return rows
