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
    weight_kg: float
    waist_cm: float
    neck_cm: float
    intake_kcal: float
    intake_is_real: bool
    steps: float
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
            waist_cm=row["waist_cm"],
            neck_cm=row["neck_cm"],
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
