"""A persisted forecast row, part of a saved forecast run (`run_id`).

Lets a saved forecast be inspected later without recomputing, with its
regression base (`base_regression`) recorded alongside it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass
class Projection:
    projection_id: int
    user_id: int
    run_id: str
    projected_date: date
    estimated_weight: float
    estimated_waist: float
    estimated_neck: float
    source_model: str
    base_regression: str
    generated_at: datetime
    activity_model: str = "constant"

    @staticmethod
    def from_row(row) -> "Projection":
        return Projection(
            projection_id=row["projection_id"],
            user_id=row["user_id"],
            run_id=row["run_id"],
            projected_date=date.fromisoformat(row["projected_date"]),
            estimated_weight=row["estimated_weight"],
            estimated_waist=row["estimated_waist"],
            estimated_neck=row["estimated_neck"],
            source_model=row["source_model"],
            base_regression=row["base_regression"],
            generated_at=datetime.fromisoformat(row["generated_at"]),
            activity_model=row["activity_model"],
        )
