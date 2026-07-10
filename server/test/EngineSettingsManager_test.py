import unittest
from datetime import date

from server.src.data.db.AuditLogDAO import AuditLogDAO
from server.src.data.db.DB import DB
from server.src.data.db.EngineSettingsDAO import EngineSettingsDAO
from server.src.data.db.UserDAO import UserDAO
from server.src.services.composition.models import DEFAULT_ENGINE_CONSTANTS
from server.src.services.EngineSettingsManager import (
    EngineSettingsManager,
    EngineSettingsManagerError,
)


class EngineSettingsManagerTest(unittest.TestCase):
    def setUp(self):
        self.db = DB(":memory:")
        self.dao = EngineSettingsDAO(self.db)
        self.audit_log_dao = AuditLogDAO(self.db)
        self.manager = EngineSettingsManager(self.dao, audit_log_dao=self.audit_log_dao)
        self.user_id = UserDAO(self.db).create(
            username="demo_cut",
            email="demo_cut@example.com",
            password_hash="hash",
            height_cm=176,
            sex=1,
            birthdate=date(2001, 8, 22),
        ).user_id

    def tearDown(self):
        self.db.close()

    def test_no_settings_yields_default_engine_constants(self):
        self.assertIsNone(self.manager.get_active(self.user_id))
        constants = self.manager.to_engine_constants(self.manager.get_active(self.user_id))
        self.assertEqual(constants, DEFAULT_ENGINE_CONSTANTS)

    def test_update_settings_partial_override_merges_onto_defaults(self):
        updated = self.manager.update_settings(self.user_id, stagnation_weeks=2)
        self.assertEqual(updated.stagnation_weeks, 2)
        self.assertEqual(updated.tef, DEFAULT_ENGINE_CONSTANTS.tef)
        self.assertEqual(updated.kcal_per_kg_fat, DEFAULT_ENGINE_CONSTANTS.kcal_per_kg_fat)

    def test_second_update_deactivates_the_first_and_merges_onto_it(self):
        first = self.manager.update_settings(self.user_id, stagnation_weeks=2)
        second = self.manager.update_settings(self.user_id, tef=0.15)

        self.assertEqual(self.manager.get_active(self.user_id).settings_id, second.settings_id)
        # tef changed, stagnation_weeks carries over from the first override.
        self.assertEqual(second.tef, 0.15)
        self.assertEqual(second.stagnation_weeks, 2)

        history = self.manager.list_history(self.user_id)
        self.assertEqual(len(history), 2)
        self.assertFalse(
            next(s for s in history if s.settings_id == first.settings_id).active
        )

    def test_rejects_unknown_field(self):
        with self.assertRaises(EngineSettingsManagerError):
            self.manager.update_settings(self.user_id, not_a_real_field=1)

    def test_rejects_out_of_bounds_values(self):
        with self.assertRaises(EngineSettingsManagerError):
            self.manager.update_settings(self.user_id, tef=1.5)
        with self.assertRaises(EngineSettingsManagerError):
            self.manager.update_settings(self.user_id, stagnation_weeks=0)
        with self.assertRaises(EngineSettingsManagerError):
            self.manager.update_settings(self.user_id, max_lean_mass_loss_share=0.0)
        with self.assertRaises(EngineSettingsManagerError):
            self.manager.update_settings(self.user_id, w_rfm=1.5)
        with self.assertRaises(EngineSettingsManagerError):
            self.manager.update_settings(self.user_id, delta=-2.0)
        with self.assertRaises(EngineSettingsManagerError):
            self.manager.update_settings(self.user_id, ffmi_coef=-1.0)
        with self.assertRaises(EngineSettingsManagerError):
            self.manager.update_settings(self.user_id, lean_tissue_kcal_per_kg=0.0)
        with self.assertRaises(EngineSettingsManagerError):
            self.manager.update_settings(self.user_id, fat_ratio_ideal=1.5)

    def test_rejects_invalid_bmr_model(self):
        with self.assertRaises(EngineSettingsManagerError):
            self.manager.update_settings(self.user_id, bmr_model="not_a_model")

    def test_accepts_valid_bmr_model(self):
        updated = self.manager.update_settings(self.user_id, bmr_model="mifflin")
        self.assertEqual(updated.bmr_model, "mifflin")

    def test_rejects_invalid_tef_mode(self):
        with self.assertRaises(EngineSettingsManagerError):
            self.manager.update_settings(self.user_id, tef_mode="not_a_mode")

    def test_accepts_valid_tef_mode_and_kappa_overrides(self):
        updated = self.manager.update_settings(
            self.user_id, tef_mode="macros", kappa_carbs=0.31, kappa_fat=0.14, kappa_protein=0.95
        )
        self.assertEqual(updated.tef_mode, "macros")
        self.assertAlmostEqual(updated.kappa_carbs, 0.31)
        self.assertAlmostEqual(updated.kappa_fat, 0.14)
        self.assertAlmostEqual(updated.kappa_protein, 0.95)

    def test_rejects_out_of_bounds_macro_kcal_mismatch_pct(self):
        with self.assertRaises(EngineSettingsManagerError):
            self.manager.update_settings(self.user_id, macro_kcal_mismatch_pct=1.5)

    def test_accepts_valid_macro_target_overrides(self):
        updated = self.manager.update_settings(
            self.user_id, protein_target_g_per_kg=2.0, fat_target_g_per_kg=0.9
        )
        self.assertAlmostEqual(updated.protein_target_g_per_kg, 2.0)
        self.assertAlmostEqual(updated.fat_target_g_per_kg, 0.9)

    def test_rejects_out_of_bounds_macro_target_deviation_pct(self):
        with self.assertRaises(EngineSettingsManagerError):
            self.manager.update_settings(self.user_id, macro_target_deviation_pct=1.5)

    def test_accepts_valid_missing_log_alert_days_override(self):
        updated = self.manager.update_settings(self.user_id, missing_log_alert_days=14)
        self.assertAlmostEqual(updated.missing_log_alert_days, 14)

    def test_rejects_out_of_bounds_missing_log_alert_days(self):
        with self.assertRaises(EngineSettingsManagerError):
            self.manager.update_settings(self.user_id, missing_log_alert_days=0.0)

    def test_bf_weights_must_sum_to_one_when_all_three_overridden(self):
        with self.assertRaises(EngineSettingsManagerError):
            self.manager.update_settings(self.user_id, w_rfm=0.6, w_navy=0.3, w_deur=0.3)

        # A valid triple (still summing to 1.0) is accepted.
        updated = self.manager.update_settings(
            self.user_id, w_rfm=0.6, w_navy=0.2, w_deur=0.2
        )
        self.assertAlmostEqual(updated.w_rfm, 0.6)

    def test_bf_weight_sum_guard_only_applies_when_all_three_are_overridden(self):
        # Overriding just one weight is accepted even though the merged
        # triple (with the other two at default) may not sum to 1.0 --
        # composition_spec.md's F8 guard only fires when all three are
        # touched together in the same call.
        updated = self.manager.update_settings(self.user_id, w_rfm=0.9)
        self.assertAlmostEqual(updated.w_rfm, 0.9)

    def test_settings_changes_are_audited(self):
        self.manager.update_settings(self.user_id, stagnation_weeks=2, tef=0.15)
        entries = self.audit_log_dao.list_for_user(self.user_id)
        entity_types = {entry.entity_type for entry in entries}
        self.assertEqual(entity_types, {"engine_settings"})
        fields_changed = {entry.field for entry in entries}
        self.assertEqual(fields_changed, {"stagnation_weeks", "tef"})

    def test_metrics_cache_is_invalidated_on_settings_change(self):
        calls = []

        class FakeMetricsCache:
            def invalidate_for_user(self, user_id):
                calls.append(user_id)

        manager = EngineSettingsManager(self.dao, metrics_cache=FakeMetricsCache())
        manager.update_settings(self.user_id, stagnation_weeks=2)
        self.assertEqual(calls, [self.user_id])


if __name__ == "__main__":
    unittest.main()
