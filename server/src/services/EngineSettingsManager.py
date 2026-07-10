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
    "bmr_model",
    "w_rfm",
    "w_navy",
    "w_deur",
    "delta",
    "ffmi_coef",
    "lean_tissue_kcal_per_kg",
    "fat_ratio_ideal",
    "reconciliation_error_threshold_kcal",
    "tef_mode",
    "kappa_carbs",
    "kappa_fat",
    "kappa_protein",
    "macro_kcal_mismatch_pct",
    "protein_target_g_per_kg",
    "fat_target_g_per_kg",
    "macro_target_deviation_pct",
    "missing_log_alert_days",
)

#: (min exclusive?, max exclusive?) sanity bounds -- generous, just enough
#: to reject nonsensical input (negative/zero denominators, fractions
#: outside 0-1, etc.), not to second-guess a user's tuning choice.
#: `bmr_model` is non-numeric and validated separately in `_validate`.
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
    "w_rfm": (0.0, 1.0),
    "w_navy": (0.0, 1.0),
    "w_deur": (0.0, 1.0),
    "delta": (-1.0, 1.0),
    "ffmi_coef": (0.0, None),
    "lean_tissue_kcal_per_kg": (0.0, None),
    "fat_ratio_ideal": (0.0, 1.0),
    "reconciliation_error_threshold_kcal": (0.0, None),
    "kappa_carbs": (0.0, None),
    "kappa_fat": (0.0, None),
    "kappa_protein": (0.0, None),
    "macro_kcal_mismatch_pct": (0.0, 1.0),
    "protein_target_g_per_kg": (0.0, None),
    "fat_target_g_per_kg": (0.0, None),
    "macro_target_deviation_pct": (0.0, 1.0),
    "missing_log_alert_days": (0.0, None),
}

_VALID_BMR_MODELS = ("cunningham", "mifflin")
_VALID_TEF_MODES = ("flat", "macros")

#: Body-fat weights must sum to 1.0 (within this tolerance) when all three
#: are overridden together in the same call -- see `update_settings`.
_WEIGHT_SUM_TOLERANCE = 1e-6
_BF_WEIGHT_FIELDS = ("w_rfm", "w_navy", "w_deur")


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
            if field == "bmr_model":
                if value not in _VALID_BMR_MODELS:
                    raise EngineSettingsManagerError(
                        f"bmr_model must be one of {_VALID_BMR_MODELS}"
                    )
                continue
            if field == "tef_mode":
                if value not in _VALID_TEF_MODES:
                    raise EngineSettingsManagerError(
                        f"tef_mode must be one of {_VALID_TEF_MODES}"
                    )
                continue
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

        if set(_BF_WEIGHT_FIELDS) <= set(overrides):
            total = sum(merged[field] for field in _BF_WEIGHT_FIELDS)
            if abs(total - 1.0) > _WEIGHT_SUM_TOLERANCE:
                raise EngineSettingsManagerError(
                    "w_rfm + w_navy + w_deur must sum to 1.0"
                )

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
