from __future__ import annotations

from datetime import date, datetime, timezone
from typing import List, Optional

from server.src.data.db.DB import DB
from server.src.data.domain.EngineSettings import EngineSettings


class EngineSettingsDAO:
    def __init__(self, db: DB):
        self.db = db

    def create(
        self,
        *,
        user_id: int,
        tef: float,
        kcal_per_kg_fat: float,
        neat_step_factor: float,
        implausible_weekly_change_pct: float,
        stagnation_weeks: int,
        stagnation_threshold_kg: float,
        lean_loss_window_weeks: int,
        max_lean_mass_loss_share: float,
        significant_deviation_kg: float,
        bmr_model: str,
        w_rfm: float,
        w_navy: float,
        w_deur: float,
        delta: float,
        ffmi_coef: float,
        lean_tissue_kcal_per_kg: float,
        fat_ratio_ideal: float,
        reconciliation_error_threshold_kcal: float,
        tef_mode: str,
        kappa_carbs: float,
        kappa_fat: float,
        kappa_protein: float,
        macro_kcal_mismatch_pct: float,
        protein_target_g_per_kg: float,
        fat_target_g_per_kg: float,
        macro_target_deviation_pct: float,
        missing_log_alert_days: float,
        start_date: date,
        active: bool = True,
    ) -> EngineSettings:
        created_at = datetime.now(timezone.utc).isoformat()
        cursor = self.db.execute(
            """
            INSERT INTO engine_settings
                (user_id, tef, kcal_per_kg_fat, neat_step_factor,
                 implausible_weekly_change_pct, stagnation_weeks,
                 stagnation_threshold_kg, lean_loss_window_weeks,
                 max_lean_mass_loss_share, significant_deviation_kg,
                 bmr_model, w_rfm, w_navy, w_deur, delta, ffmi_coef,
                 lean_tissue_kcal_per_kg, fat_ratio_ideal,
                 reconciliation_error_threshold_kcal,
                 tef_mode, kappa_carbs, kappa_fat, kappa_protein,
                 macro_kcal_mismatch_pct,
                 protein_target_g_per_kg, fat_target_g_per_kg,
                 macro_target_deviation_pct, missing_log_alert_days,
                 start_date, active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                tef,
                kcal_per_kg_fat,
                neat_step_factor,
                implausible_weekly_change_pct,
                stagnation_weeks,
                stagnation_threshold_kg,
                lean_loss_window_weeks,
                max_lean_mass_loss_share,
                significant_deviation_kg,
                bmr_model,
                w_rfm,
                w_navy,
                w_deur,
                delta,
                ffmi_coef,
                lean_tissue_kcal_per_kg,
                fat_ratio_ideal,
                reconciliation_error_threshold_kcal,
                tef_mode,
                kappa_carbs,
                kappa_fat,
                kappa_protein,
                macro_kcal_mismatch_pct,
                protein_target_g_per_kg,
                fat_target_g_per_kg,
                macro_target_deviation_pct,
                missing_log_alert_days,
                start_date.isoformat(),
                int(active),
                created_at,
            ),
        )
        return self.get_by_id(cursor.lastrowid)

    def get_by_id(self, settings_id: int) -> Optional[EngineSettings]:
        row = self.db.query_one(
            "SELECT * FROM engine_settings WHERE settings_id = ?", (settings_id,)
        )
        return EngineSettings.from_row(row) if row else None

    def get_active(self, user_id: int) -> Optional[EngineSettings]:
        row = self.db.query_one(
            """
            SELECT * FROM engine_settings
            WHERE user_id = ? AND active = 1
            ORDER BY start_date DESC, settings_id DESC
            LIMIT 1
            """,
            (user_id,),
        )
        return EngineSettings.from_row(row) if row else None

    def list_for_user(self, user_id: int) -> List[EngineSettings]:
        rows = self.db.query(
            """
            SELECT * FROM engine_settings
            WHERE user_id = ?
            ORDER BY start_date DESC, settings_id DESC
            """,
            (user_id,),
        )
        return [EngineSettings.from_row(row) for row in rows]

    def deactivate(self, settings_id: int) -> None:
        self.db.execute(
            "UPDATE engine_settings SET active = 0 WHERE settings_id = ?", (settings_id,)
        )
