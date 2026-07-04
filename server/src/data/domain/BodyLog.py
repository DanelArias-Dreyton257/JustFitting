"""Persisted weekly body-composition measurement (real or projected)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


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
        )
