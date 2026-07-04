from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from server.src.data.domain.EngineSettings import EngineSettings


@dataclass(frozen=True)
class EngineSettingsDTO:
    tef: float
    kcal_per_kg_fat: float
    neat_step_factor: float
    implausible_weekly_change_pct: float
    stagnation_weeks: int
    stagnation_threshold_kg: float
    lean_loss_window_weeks: int
    max_lean_mass_loss_share: float
    significant_deviation_kg: float
    bmr_model: str
    w_rfm: float
    w_navy: float
    w_deur: float
    delta: float
    ffmi_coef: float
    lean_tissue_kcal_per_kg: float
    fat_ratio_ideal: float
    reconciliation_error_threshold_kcal: float
    tef_mode: str
    kappa_carbs: float
    kappa_fat: float
    kappa_protein: float
    macro_kcal_mismatch_pct: float
    protein_target_g_per_kg: float
    fat_target_g_per_kg: float
    macro_target_deviation_pct: float
    is_default: bool
    settings_id: Optional[int] = None
    start_date: Optional[str] = None
    active: Optional[bool] = None
    created_at: Optional[str] = None

    @staticmethod
    def from_domain(settings: Optional[EngineSettings]) -> "EngineSettingsDTO":
        from server.src.services.composition.models import DEFAULT_ENGINE_CONSTANTS

        if settings is None:
            defaults = DEFAULT_ENGINE_CONSTANTS
            return EngineSettingsDTO(
                tef=defaults.tef,
                kcal_per_kg_fat=defaults.kcal_per_kg_fat,
                neat_step_factor=defaults.neat_step_factor,
                implausible_weekly_change_pct=defaults.implausible_weekly_change_pct,
                stagnation_weeks=defaults.stagnation_weeks,
                stagnation_threshold_kg=defaults.stagnation_threshold_kg,
                lean_loss_window_weeks=defaults.lean_loss_window_weeks,
                max_lean_mass_loss_share=defaults.max_lean_mass_loss_share,
                significant_deviation_kg=defaults.significant_deviation_kg,
                bmr_model=defaults.bmr_model,
                w_rfm=defaults.w_rfm,
                w_navy=defaults.w_navy,
                w_deur=defaults.w_deur,
                delta=defaults.delta,
                ffmi_coef=defaults.ffmi_coef,
                lean_tissue_kcal_per_kg=defaults.lean_tissue_kcal_per_kg,
                fat_ratio_ideal=defaults.fat_ratio_ideal,
                reconciliation_error_threshold_kcal=defaults.reconciliation_error_threshold_kcal,
                tef_mode=defaults.tef_mode,
                kappa_carbs=defaults.kappa_carbs,
                kappa_fat=defaults.kappa_fat,
                kappa_protein=defaults.kappa_protein,
                macro_kcal_mismatch_pct=defaults.macro_kcal_mismatch_pct,
                protein_target_g_per_kg=defaults.protein_target_g_per_kg,
                fat_target_g_per_kg=defaults.fat_target_g_per_kg,
                macro_target_deviation_pct=defaults.macro_target_deviation_pct,
                is_default=True,
            )
        return EngineSettingsDTO(
            tef=settings.tef,
            kcal_per_kg_fat=settings.kcal_per_kg_fat,
            neat_step_factor=settings.neat_step_factor,
            implausible_weekly_change_pct=settings.implausible_weekly_change_pct,
            stagnation_weeks=settings.stagnation_weeks,
            stagnation_threshold_kg=settings.stagnation_threshold_kg,
            lean_loss_window_weeks=settings.lean_loss_window_weeks,
            max_lean_mass_loss_share=settings.max_lean_mass_loss_share,
            significant_deviation_kg=settings.significant_deviation_kg,
            bmr_model=settings.bmr_model,
            w_rfm=settings.w_rfm,
            w_navy=settings.w_navy,
            w_deur=settings.w_deur,
            delta=settings.delta,
            ffmi_coef=settings.ffmi_coef,
            lean_tissue_kcal_per_kg=settings.lean_tissue_kcal_per_kg,
            fat_ratio_ideal=settings.fat_ratio_ideal,
            reconciliation_error_threshold_kcal=settings.reconciliation_error_threshold_kcal,
            tef_mode=settings.tef_mode,
            kappa_carbs=settings.kappa_carbs,
            kappa_fat=settings.kappa_fat,
            kappa_protein=settings.kappa_protein,
            macro_kcal_mismatch_pct=settings.macro_kcal_mismatch_pct,
            protein_target_g_per_kg=settings.protein_target_g_per_kg,
            fat_target_g_per_kg=settings.fat_target_g_per_kg,
            macro_target_deviation_pct=settings.macro_target_deviation_pct,
            is_default=False,
            settings_id=settings.settings_id,
            start_date=settings.start_date.isoformat(),
            active=settings.active,
            created_at=settings.created_at.isoformat(),
        )
