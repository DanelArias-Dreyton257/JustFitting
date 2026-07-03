"""Historized per-user engine tunables (energy-model constants + Phase 1.3
alert thresholds).

Follows the same historization pattern as ``GoalPlan`` (Phase 1.1): every
change creates a new row and deactivates the previous one, instead of
overwriting values in place.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass
class EngineSettings:
    settings_id: int
    user_id: int
    tef: float
    kcal_per_kg_fat: float
    neat_step_factor: float
    implausible_weekly_change_pct: float
    stagnation_weeks: int
    stagnation_threshold_kg: float
    lean_loss_window_weeks: int
    max_lean_mass_loss_share: float
    significant_deviation_kg: float
    start_date: date
    active: bool
    created_at: datetime

    @staticmethod
    def from_row(row) -> "EngineSettings":
        return EngineSettings(
            settings_id=row["settings_id"],
            user_id=row["user_id"],
            tef=row["tef"],
            kcal_per_kg_fat=row["kcal_per_kg_fat"],
            neat_step_factor=row["neat_step_factor"],
            implausible_weekly_change_pct=row["implausible_weekly_change_pct"],
            stagnation_weeks=row["stagnation_weeks"],
            stagnation_threshold_kg=row["stagnation_threshold_kg"],
            lean_loss_window_weeks=row["lean_loss_window_weeks"],
            max_lean_mass_loss_share=row["max_lean_mass_loss_share"],
            significant_deviation_kg=row["significant_deviation_kg"],
            start_date=date.fromisoformat(row["start_date"]),
            active=bool(row["active"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )
