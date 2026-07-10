"""Persisted weekly body-composition measurement (real or projected)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional


@dataclass
class BodyLog:
    log_id: int
    user_id: int
    date: date
    # Phase 7.4 (partial logs, see README): individually optional -- a row
    # can be missing any subset of these until completed by a later merge
    # (LogManager.upsert_fields) or edit. `None` means "not logged yet by
    # any source," distinct from `0.0`. Phase 9.1: waist_cm/neck_cm moved
    # off this model entirely -- see data/domain/BodyMeasurement.py.
    weight_kg: Optional[float]
    intake_kcal: Optional[float]
    intake_is_real: bool
    steps: Optional[float]
    cardio_kcal: float
    source: str  # "real" | "projected"
    created_at: datetime
    granularity: str = "weekly"  # "daily" | "weekly"
    # Phase 3.4 (Wave 2, F9): together or not at all (see
    # CompositionEngine.validate_log_input); meaningful mainly on a
    # daily-granularity row, but not restricted to one.
    carbs_g: Optional[float] = None
    fat_g: Optional[float] = None
    protein_g: Optional[float] = None

    @staticmethod
    def from_row(row) -> "BodyLog":
        return BodyLog(
            log_id=row["log_id"],
            user_id=row["user_id"],
            date=date.fromisoformat(row["date"]),
            weight_kg=row["weight_kg"],
            intake_kcal=row["intake_kcal"],
            intake_is_real=bool(row["intake_is_real"]),
            steps=row["steps"],
            cardio_kcal=row["cardio_kcal"],
            source=row["source"],
            created_at=datetime.fromisoformat(row["created_at"]),
            granularity=row["granularity"],
            carbs_g=row["carbs_g"],
            fat_g=row["fat_g"],
            protein_g=row["protein_g"],
        )
