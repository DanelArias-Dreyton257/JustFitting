"""Golden acceptance test for the composition engine (see docs/composition_spec.md).

Reference profile: H=176, sex=1 (male), birthdate=2001-08-22, target_bf=0.15,
weekly_rate=-0.005. Values are checked against the verified "Danel" reference
with a tolerance of +/-0.01 (+/-0.5 kcal for calorie figures).
"""

import unittest
from datetime import date

from server.src.services.composition import (
    Anthropometry,
    CompositionEngine,
    EnergyModel,
    Projection,
)
from server.src.services.composition.models import EngineConstants, LogInput, ProfileParams

PROFILE = ProfileParams(
    height_cm=176,
    sex=1,
    birthdate=date(2001, 8, 22),
    target_bf=0.15,
    weekly_rate=-0.005,
)


class CompositionEngineGoldenTest(unittest.TestCase):
    def test_first_record_base_case(self):
        log = LogInput(
            date=date(2025, 12, 28),
            weight_kg=97.0,
            waist_cm=91.0,
            neck_cm=38.5,
            intake_kcal=2400.0,
            steps=6000,
        )
        result = CompositionEngine.compute_row(PROFILE, log, prev_weight_kg=None)

        self.assertAlmostEqual(result.bmi, 31.31, delta=0.01)
        self.assertAlmostEqual(result.body_fat, 0.2459, delta=0.01)
        self.assertAlmostEqual(result.fat_mass_kg, 23.85, delta=0.01)
        self.assertAlmostEqual(result.lean_mass_kg, 73.15, delta=0.01)

        # Base-case trajectory fields for the first row in a series.
        self.assertEqual(result.weight_delta_kg, 0.0)
        self.assertEqual(result.weight_delta_pct, 0.0)
        self.assertEqual(result.weight_objective_kg, log.weight_kg)
        self.assertEqual(result.weight_to_shed_kg, 0.0)
        self.assertEqual(result.weekly_deficit_kcal, 0.0)
        self.assertEqual(result.daily_deficit_kcal, 0.0)
        self.assertAlmostEqual(result.target_calories, result.tdee, delta=0.5)

    def test_last_record(self):
        prior_week = LogInput(
            date=date(2026, 6, 19),
            weight_kg=91.0,
            waist_cm=80.5,
            neck_cm=35.0,
            intake_kcal=2050.0,
            steps=5200,
        )
        last_week = LogInput(
            date=date(2026, 6, 26),
            weight_kg=90.7,
            waist_cm=80.0,
            neck_cm=35.0,
            intake_kcal=2014.30,
            steps=5000,
        )
        results = CompositionEngine.compute_series(PROFILE, [prior_week, last_week])
        result = results[-1]

        self.assertAlmostEqual(result.bmi, 29.28, delta=0.01)
        self.assertAlmostEqual(result.rfm, 0.2000, delta=0.01)
        self.assertAlmostEqual(result.navy, 0.1519, delta=0.01)
        self.assertAlmostEqual(result.deurenberg, 0.2446, delta=0.01)
        self.assertAlmostEqual(result.body_fat, 0.1991, delta=0.01)
        self.assertAlmostEqual(result.fat_mass_kg, 18.06, delta=0.01)
        self.assertAlmostEqual(result.lean_mass_kg, 72.64, delta=0.01)
        self.assertAlmostEqual(result.ffmi, 23.45, delta=0.01)
        self.assertAlmostEqual(result.ffmi_adj, 23.70, delta=0.01)

        self.assertAlmostEqual(result.bmr, 2098.08, delta=0.5)
        self.assertAlmostEqual(result.neat, 226.75, delta=0.5)
        self.assertAlmostEqual(result.tdee, 2583.14, delta=0.5)
        self.assertAlmostEqual(result.target_calories, 2027.03, delta=0.5)
        self.assertAlmostEqual(result.intake_diff, -12.73, delta=0.5)

        self.assertAlmostEqual(result.weight_objective_kg, 90.545, delta=0.01)
        self.assertAlmostEqual(result.weight_gap_kg, 0.155, delta=0.01)
        self.assertAlmostEqual(result.weight_delta_kg, -0.3, delta=0.01)
        self.assertAlmostEqual(result.daily_deficit_kcal, 500.5, delta=0.5)
        self.assertAlmostEqual(result.final_weight_kg, 85.459, delta=0.01)
        self.assertAlmostEqual(result.weeks_to_goal, 11.93, delta=0.01)
        self.assertAlmostEqual(result.above_target, 0.0491, delta=0.01)

    def test_navy_guard_rejects_waist_not_greater_than_neck(self):
        log = LogInput(
            date=date(2026, 1, 1),
            weight_kg=90.0,
            waist_cm=35.0,
            neck_cm=35.0,
            intake_kcal=2000.0,
            steps=5000,
        )
        with self.assertRaises(ValueError):
            CompositionEngine.compute_row(PROFILE, log, prev_weight_kg=None)

    def test_validation_rejects_non_positive_inputs(self):
        log = LogInput(
            date=date(2026, 1, 1),
            weight_kg=0,
            waist_cm=80.0,
            neck_cm=35.0,
            intake_kcal=2000.0,
            steps=5000,
        )
        with self.assertRaises(ValueError):
            CompositionEngine.compute_row(PROFILE, log, prev_weight_kg=None)

    def test_projection_advances_weekly_and_flags_assumed_intake(self):
        real_logs = [
            LogInput(
                date=date(2025, 12, 28),
                weight_kg=97.0,
                waist_cm=91.0,
                neck_cm=38.5,
                intake_kcal=2400.0,
                steps=6000,
            ),
            LogInput(
                date=date(2026, 1, 4),
                weight_kg=96.4,
                waist_cm=90.5,
                neck_cm=38.5,
                intake_kcal=2350.0,
                steps=6200,
            ),
        ]
        projected = Projection.project_series(PROFILE, real_logs, weeks=3)

        self.assertEqual(len(projected), 3)
        prev_date = real_logs[-1].date
        for result in projected:
            self.assertEqual((result.date - prev_date).days, 7)
            self.assertEqual(result.source, "projected")
            prev_date = result.date


class EngineConstantsOverrideTest(unittest.TestCase):
    """Phase 1.5: per-user overridable energy constants. Omitting
    `engine_constants` must reproduce today's fixed `constants.py` values
    exactly (the golden tests above already pin that); these cover that an
    explicit override actually changes the computed row."""

    LOG = LogInput(
        date=date(2026, 6, 26),
        weight_kg=90.7,
        waist_cm=80.0,
        neck_cm=35.0,
        intake_kcal=2014.30,
        steps=5000,
    )

    def test_default_engine_constants_matches_no_override(self):
        default_result = CompositionEngine.compute_row(PROFILE, self.LOG)
        explicit_result = CompositionEngine.compute_row(
            PROFILE, self.LOG, engine_constants=EngineConstants()
        )
        self.assertEqual(default_result, explicit_result)

    def test_custom_tef_changes_target_calories_and_tdee(self):
        default_result = CompositionEngine.compute_row(PROFILE, self.LOG)
        custom = CompositionEngine.compute_row(
            PROFILE, self.LOG, engine_constants=EngineConstants(tef=0.20)
        )
        self.assertNotAlmostEqual(custom.tdee, default_result.tdee, delta=0.01)
        self.assertNotAlmostEqual(
            custom.target_calories, default_result.target_calories, delta=0.01
        )

    def test_custom_neat_step_factor_changes_neat(self):
        custom = CompositionEngine.compute_row(
            PROFILE, self.LOG, engine_constants=EngineConstants(neat_step_factor=1.0)
        )
        expected_neat = 1.0 * self.LOG.weight_kg * (self.LOG.steps / 1000)
        self.assertAlmostEqual(custom.neat, expected_neat, delta=0.01)

    def test_custom_kcal_per_kg_fat_changes_weekly_deficit(self):
        prior_week = LogInput(
            date=date(2026, 6, 19),
            weight_kg=91.0,
            waist_cm=80.5,
            neck_cm=35.0,
            intake_kcal=2050.0,
            steps=5200,
        )
        default_results = CompositionEngine.compute_series(PROFILE, [prior_week, self.LOG])
        custom_results = CompositionEngine.compute_series(
            PROFILE,
            [prior_week, self.LOG],
            engine_constants=EngineConstants(kcal_per_kg_fat=9000.0),
        )
        self.assertNotAlmostEqual(
            custom_results[-1].weekly_deficit_kcal,
            default_results[-1].weekly_deficit_kcal,
            delta=0.5,
        )

    def test_custom_implausible_threshold_changes_the_warning_boundary(self):
        prior_week = LogInput(
            date=date(2026, 6, 19),
            weight_kg=91.0,
            waist_cm=80.5,
            neck_cm=35.0,
            intake_kcal=2050.0,
            steps=5200,
        )
        # A 5% swing wouldn't warn at the default 8% threshold, but should
        # at a tightened 3% threshold.
        swing_log = LogInput(
            date=date(2026, 6, 26),
            weight_kg=prior_week.weight_kg * 0.95,
            waist_cm=80.0,
            neck_cm=35.0,
            intake_kcal=2000.0,
            steps=5000,
        )
        with self.assertWarns(UserWarning):
            CompositionEngine.compute_row(
                PROFILE,
                swing_log,
                prev_weight_kg=prior_week.weight_kg,
                engine_constants=EngineConstants(implausible_weekly_change_pct=0.03),
            )

    def test_custom_bmr_model_switches_to_mifflin(self):
        default_result = CompositionEngine.compute_row(PROFILE, self.LOG)
        custom = CompositionEngine.compute_row(
            PROFILE, self.LOG, engine_constants=EngineConstants(bmr_model="mifflin")
        )
        age = Anthropometry.compute_age(self.LOG.date, PROFILE.birthdate)
        expected_bmr = EnergyModel.compute_bmr_mifflin(
            self.LOG.weight_kg, PROFILE.height_cm, age, PROFILE.sex
        )
        self.assertAlmostEqual(custom.bmr, expected_bmr, delta=0.01)
        self.assertNotAlmostEqual(custom.bmr, default_result.bmr, delta=0.5)

    def test_custom_bf_weights_change_body_fat(self):
        default_result = CompositionEngine.compute_row(PROFILE, self.LOG)
        custom = CompositionEngine.compute_row(
            PROFILE,
            self.LOG,
            engine_constants=EngineConstants(w_rfm=1.0, w_navy=0.0, w_deur=0.0),
        )
        self.assertAlmostEqual(custom.body_fat, default_result.rfm, delta=0.001)
        self.assertNotAlmostEqual(custom.body_fat, default_result.body_fat, delta=1e-4)

    def test_custom_delta_offsets_body_fat(self):
        default_result = CompositionEngine.compute_row(PROFILE, self.LOG)
        custom = CompositionEngine.compute_row(
            PROFILE, self.LOG, engine_constants=EngineConstants(delta=0.02)
        )
        self.assertAlmostEqual(
            custom.body_fat, default_result.body_fat + 0.02, delta=0.001
        )

    def test_custom_ffmi_coef_changes_ffmi_adjusted(self):
        default_result = CompositionEngine.compute_row(PROFILE, self.LOG)
        custom = CompositionEngine.compute_row(
            PROFILE, self.LOG, engine_constants=EngineConstants(ffmi_coef=10.0)
        )
        height_m = PROFILE.height_cm / 100
        expected_delta = (10.0 - 6.3) * (1.80 - height_m)
        self.assertAlmostEqual(
            custom.ffmi_adj, default_result.ffmi_adj + expected_delta, delta=0.001
        )

    def test_bulk_profile_uses_reconciled_formula_with_mifflin_bmr(self):
        """Phase 3, F1/F4: a bulk goal (weekly_rate > 0) reuses the exact
        same Pi_i/deficit chain (which goes negative, i.e. a surplus) and
        the Mifflin BMR model wires through the same compute_row path as
        the default cut/Cunningham profile above."""
        bulk_profile = ProfileParams(
            height_cm=194,
            sex=1,
            birthdate=date(2001, 4, 5),
            target_bf=0.15,
            weekly_rate=0.005,
        )
        prior = LogInput(
            date=date(2026, 6, 19),
            weight_kg=95.0,
            waist_cm=90.0,
            neck_cm=40.0,
            intake_kcal=3200.0,
            steps=8000,
        )
        log = LogInput(
            date=date(2026, 6, 26),
            weight_kg=95.3,
            waist_cm=90.1,
            neck_cm=40.0,
            intake_kcal=3200.0,
            steps=8000,
        )
        ec = EngineConstants(bmr_model="mifflin")
        results = CompositionEngine.compute_series(
            bulk_profile, [prior, log], engine_constants=ec
        )
        result = results[-1]

        age = Anthropometry.compute_age(log.date, bulk_profile.birthdate)
        expected_bmr = EnergyModel.compute_bmr_mifflin(
            log.weight_kg, bulk_profile.height_cm, age, bulk_profile.sex
        )
        self.assertAlmostEqual(result.bmr, expected_bmr, delta=0.01)

        expected_neat = EnergyModel.compute_neat(log.weight_kg, log.steps, ec.neat_step_factor)
        expected_tdee = EnergyModel.compute_tdee(expected_bmr, expected_neat, ec.tef)
        self.assertAlmostEqual(result.tdee, expected_tdee, delta=0.01)

        # Bulk: Pi_i = W_{i-1} - Wobj_i goes negative (a surplus), since
        # Wobj_i = W_{i-1}*(1+rho) > W_{i-1} for rho > 0.
        self.assertLess(result.weight_to_shed_kg, 0)
        self.assertLess(result.daily_deficit_kcal, 0)

    def test_cardio_kcal_raises_tdee_and_target_calories(self):
        """Phase 3.1, F2: cardio_kcal (EAT) folds into TDEE/target-calories
        as an additive term -- with cardio_kcal=0 (every pre-existing log)
        this is byte-for-byte identical to before (the golden tests above
        already pin that); this covers the nonzero case."""
        no_cardio = LogInput(
            date=self.LOG.date,
            weight_kg=self.LOG.weight_kg,
            waist_cm=self.LOG.waist_cm,
            neck_cm=self.LOG.neck_cm,
            intake_kcal=self.LOG.intake_kcal,
            steps=self.LOG.steps,
            cardio_kcal=0.0,
        )
        with_cardio = LogInput(
            date=self.LOG.date,
            weight_kg=self.LOG.weight_kg,
            waist_cm=self.LOG.waist_cm,
            neck_cm=self.LOG.neck_cm,
            intake_kcal=self.LOG.intake_kcal,
            steps=self.LOG.steps,
            cardio_kcal=300.0,
        )
        base_result = CompositionEngine.compute_row(PROFILE, no_cardio)
        cardio_result = CompositionEngine.compute_row(PROFILE, with_cardio)

        expected_increase = 300.0 / (1 - EngineConstants().tef)
        self.assertAlmostEqual(
            cardio_result.tdee, base_result.tdee + expected_increase, delta=0.01
        )
        self.assertAlmostEqual(
            cardio_result.target_calories,
            base_result.target_calories + expected_increase,
            delta=0.01,
        )


class MacroTefTest(unittest.TestCase):
    """Phase 3.4, F9: TEF computed directly from logged macro grams."""

    LOG = LogInput(
        date=date(2026, 6, 26),
        weight_kg=90.7,
        waist_cm=80.0,
        neck_cm=35.0,
        intake_kcal=2014.30,
        steps=5000,
    )
    WITH_MACROS = LogInput(
        date=date(2026, 6, 26),
        weight_kg=90.7,
        waist_cm=80.0,
        neck_cm=35.0,
        intake_kcal=2014.30,
        steps=5000,
        carbs_g=200.0,
        fat_g=70.0,
        protein_g=180.0,
    )

    def test_default_flat_mode_is_unaffected_by_logged_macros(self):
        """tef_mode defaults to "flat" -- logging macros without opting in
        must not change the result at all (byte-for-byte, like cardio_kcal=0)."""
        without = CompositionEngine.compute_row(PROFILE, self.LOG)
        with_macros_but_flat_mode = CompositionEngine.compute_row(PROFILE, self.WITH_MACROS)
        self.assertEqual(without.tdee, with_macros_but_flat_mode.tdee)
        self.assertEqual(without.target_calories, with_macros_but_flat_mode.target_calories)
        self.assertEqual(with_macros_but_flat_mode.tef_mode, "flat")

    def test_macros_mode_switches_to_the_additive_formula(self):
        ec = EngineConstants(tef_mode="macros")
        result = CompositionEngine.compute_row(PROFILE, self.WITH_MACROS, engine_constants=ec)

        expected_tef_kcal = (
            ec.kappa_carbs * 200.0 + ec.kappa_fat * 70.0 + ec.kappa_protein * 180.0
        )
        expected_tdee = result.bmr + result.neat + self.WITH_MACROS.cardio_kcal + expected_tef_kcal
        self.assertEqual(result.tef_mode, "macros")
        self.assertAlmostEqual(result.tef_kcal, expected_tef_kcal, delta=1e-9)
        self.assertAlmostEqual(result.tdee, expected_tdee, delta=1e-9)

    def test_macros_mode_falls_back_to_flat_when_a_week_has_no_macros(self):
        """A week with no macros logged degrades to flat automatically, even
        when the account's tef_mode is "macros" -- additive, never blocking."""
        ec = EngineConstants(tef_mode="macros")
        flat_result = CompositionEngine.compute_row(PROFILE, self.LOG)
        macros_setting_no_data = CompositionEngine.compute_row(
            PROFILE, self.LOG, engine_constants=ec
        )
        self.assertEqual(macros_setting_no_data.tef_mode, "flat")
        self.assertAlmostEqual(macros_setting_no_data.tdee, flat_result.tdee, delta=0.01)

    def test_flat_mode_tef_kcal_matches_the_implied_divisor_share(self):
        result = CompositionEngine.compute_row(PROFILE, self.LOG)
        self.assertAlmostEqual(result.tef_kcal, result.tdee * EngineConstants().tef, delta=1e-9)

    def test_partial_macros_are_rejected(self):
        partial = LogInput(
            date=date(2026, 6, 26),
            weight_kg=90.7,
            waist_cm=80.0,
            neck_cm=35.0,
            intake_kcal=2014.30,
            steps=5000,
            carbs_g=200.0,
            fat_g=None,
            protein_g=180.0,
        )
        with self.assertRaises(ValueError):
            CompositionEngine.compute_row(PROFILE, partial)

    def test_negative_macro_is_rejected(self):
        negative = LogInput(
            date=date(2026, 6, 26),
            weight_kg=90.7,
            waist_cm=80.0,
            neck_cm=35.0,
            intake_kcal=2014.30,
            steps=5000,
            carbs_g=-1.0,
            fat_g=70.0,
            protein_g=180.0,
        )
        with self.assertRaises(ValueError):
            CompositionEngine.compute_row(PROFILE, negative)


if __name__ == "__main__":
    unittest.main()
