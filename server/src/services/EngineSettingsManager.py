"""Historized engine-tunable CRUD: every settings change creates a new
`EngineSettings` row and deactivates the previous one -- the same
create-new/deactivate-old/audit/cache-invalidate pattern as
`GoalPlanManager` (Phase 1.1), applied to the Phase 1.5 energy-model
constants and alert thresholds instead of target-BF/weekly-rate.
"""

from __future__ import annotations

from datetime import date
from typing import List, Optional

from server.src.data.db.AuditLogDAO import AuditLogDAO
from server.src.data.db.EngineSettingsDAO import EngineSettingsDAO
from server.src.data.domain.EngineSettings import EngineSettings
from server.src.services.composition.models import DEFAULT_ENGINE_CONSTANTS, EngineConstants

#: Every user-tunable field, in the order `EngineConstants` declares them.
FIELDS = (
    "tef",
    "kcal_per_kg_fat",
    "neat_step_factor",
    "implausible_weekly_change_pct",
    "stagnation_weeks",
    "stagnation_threshold_kg",
    "lean_loss_window_weeks",
    "max_lean_mass_loss_share",
    "significant_deviation_kg",
)

#: (min exclusive?, max exclusive?) sanity bounds -- generous, just enough
#: to reject nonsensical input (negative/zero denominators, fractions
#: outside 0-1, etc.), not to second-guess a user's tuning choice.
_BOUNDS = {
    "tef": (0.0, 1.0),
    "kcal_per_kg_fat": (0.0, None),
    "neat_step_factor": (0.0, None),
    "implausible_weekly_change_pct": (0.0, 1.0),
    "stagnation_weeks": (0, None),
    "stagnation_threshold_kg": (0.0, None),
    "lean_loss_window_weeks": (0, None),
    "max_lean_mass_loss_share": (0.0, 1.0),
    "significant_deviation_kg": (0.0, None),
}


class EngineSettingsManagerError(Exception):
    """Raised for invalid engine-settings parameters."""


class EngineSettingsManager:
    def __init__(
        self,
        engine_settings_dao: EngineSettingsDAO,
        audit_log_dao: Optional[AuditLogDAO] = None,
        metrics_cache=None,
    ):
        self.engine_settings_dao = engine_settings_dao
        self.audit_log_dao = audit_log_dao
        self.metrics_cache = metrics_cache

    def get_active(self, user_id: int) -> Optional[EngineSettings]:
        return self.engine_settings_dao.get_active(user_id)

    def list_history(self, user_id: int) -> List[EngineSettings]:
        return self.engine_settings_dao.list_for_user(user_id)

    @staticmethod
    def to_engine_constants(settings: Optional[EngineSettings]) -> EngineConstants:
        """Defaults are today's fixed `constants.py` values when a user has
        never overridden anything."""
        if settings is None:
            return DEFAULT_ENGINE_CONSTANTS
        return EngineConstants(**{field: getattr(settings, field) for field in FIELDS})

    @staticmethod
    def _validate(values: dict) -> None:
        for field, value in values.items():
            low, high = _BOUNDS[field]
            if low is not None and value <= low:
                raise EngineSettingsManagerError(f"{field} must be greater than {low}")
            if high is not None and value > high:
                raise EngineSettingsManagerError(f"{field} must be at most {high}")

    def update_settings(self, user_id: int, **overrides) -> EngineSettings:
        unknown = set(overrides) - set(FIELDS)
        if unknown:
            raise EngineSettingsManagerError(
                f"unknown settings field(s): {sorted(unknown)}"
            )

        previous = self.engine_settings_dao.get_active(user_id)
        base = self.to_engine_constants(previous)
        merged = {field: overrides.get(field, getattr(base, field)) for field in FIELDS}
        self._validate(merged)

        if previous is not None:
            self.engine_settings_dao.deactivate(previous.settings_id)
            if self.audit_log_dao is not None:
                self.audit_log_dao.record(
                    user_id=user_id,
                    entity_type="engine_settings",
                    entity_id=previous.settings_id,
                    field="active",
                    previous_value="1",
                    new_value="0",
                )

        new_settings = self.engine_settings_dao.create(
            user_id=user_id, start_date=date.today(), active=True, **merged
        )

        if self.audit_log_dao is not None:
            for field in overrides:
                previous_value = getattr(base, field)
                new_value = merged[field]
                if previous_value != new_value:
                    self.audit_log_dao.record(
                        user_id=user_id,
                        entity_type="engine_settings",
                        entity_id=new_settings.settings_id,
                        field=field,
                        previous_value=str(previous_value),
                        new_value=str(new_value),
                    )

        if self.metrics_cache is not None:
            self.metrics_cache.invalidate_for_user(user_id)

        return new_settings
