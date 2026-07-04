"""Gain-quality tracking (Phase 3.1, F3): each test builds the minimal
`CompositionResult` series needed, since `GainQuality.compute_gain_quality`
only reads `lean_mass_kg`/`fat_mass_kg`/`date` from each row (see
GainQuality.py's module docstring)."""

import unittest
from datetime import date, timedelta

from server.src.services.composition import CompositionEngine
from server.src.services.composition.GainQuality import compute_gain_quality
from server.src.services.composition.models import CompositionResult, LogInput, ProfileParams

BASE_DATE = date(2026, 1, 4)


def make_result(week_offset: int = 0, **overrides) -> CompositionResult:
    defaults = dict(
        date=BASE_DATE + timedelta(days=7 * week_offset),
        age=24,
        bmi=28.0,
        ffmi=22.0,
        ffmi_adj=22.0,
        rfm=0.2,
        navy=0.2,
        deurenberg=0.2,
        body_fat=0.2,
        fat_mass_kg=18.0,
        lean_mass_kg=72.0,
        above_target=0.05,
        bmr=2000.0,
        neat=200.0,
        tdee=2400.0,
        target_calories=2000.0,
        intake_diff=0.0,
        weight_delta_kg=0.0,
        weight_delta_pct=0.0,
        weight_objective_kg=90.0,
        weight_gap_kg=0.0,
        weight_to_shed_kg=0.0,
        weekly_deficit_kcal=0.0,
        daily_deficit_kcal=0.0,
        final_weight_kg=85.0,
        weeks_to_goal=10.0,
        source="real",
    )
    defaults.update(overrides)
    return CompositionResult(**defaults)


class GainQualityTest(unittest.TestCase):
    def test_first_row_is_the_base_case(self):
        rows = compute_gain_quality([make_result(0, fat_mass_kg=18.0, lean_mass_kg=72.0)])
        self.assertEqual(rows[0].delta_lean_kg, 0.0)
        self.assertEqual(rows[0].delta_fat_kg, 0.0)
        self.assertEqual(rows[0].delta_lean_kg_cum, 0.0)
        self.assertEqual(rows[0].delta_fat_kg_cum, 0.0)
        self.assertIsNone(rows[0].fat_ratio)
        self.assertIsNone(rows[0].fat_ratio_cumulative)

    def test_computes_deltas_and_fat_ratio_for_a_clean_gain(self):
        results = [
            make_result(0, fat_mass_kg=18.0, lean_mass_kg=72.0),
            make_result(1, fat_mass_kg=18.2, lean_mass_kg=72.6),  # +0.2 fat, +0.6 lean
        ]
        rows = compute_gain_quality(results)
        self.assertAlmostEqual(rows[1].delta_fat_kg, 0.2, delta=1e-9)
        self.assertAlmostEqual(rows[1].delta_lean_kg, 0.6, delta=1e-9)
        self.assertAlmostEqual(rows[1].fat_ratio, 0.2 / 0.8, delta=1e-9)

    def test_cumulative_sums_accumulate_across_weeks(self):
        results = [
            make_result(0, fat_mass_kg=18.0, lean_mass_kg=72.0),
            make_result(1, fat_mass_kg=18.2, lean_mass_kg=72.6),
            make_result(2, fat_mass_kg=18.5, lean_mass_kg=73.0),
        ]
        rows = compute_gain_quality(results)
        self.assertAlmostEqual(rows[2].delta_fat_kg_cum, 0.5, delta=1e-9)
        self.assertAlmostEqual(rows[2].delta_lean_kg_cum, 1.0, delta=1e-9)
        self.assertAlmostEqual(rows[2].fat_ratio_cumulative, 0.5 / 1.5, delta=1e-9)

    def test_fat_ratio_is_none_when_weight_is_unchanged(self):
        results = [
            make_result(0, fat_mass_kg=18.0, lean_mass_kg=72.0),
            # +0.3 fat, -0.3 lean: net weight change is zero.
            make_result(1, fat_mass_kg=18.3, lean_mass_kg=71.7),
        ]
        rows = compute_gain_quality(results)
        self.assertIsNone(rows[1].fat_ratio)

    def test_handles_a_loss_week_with_negative_deltas(self):
        results = [
            make_result(0, fat_mass_kg=18.0, lean_mass_kg=72.0),
            make_result(1, fat_mass_kg=17.5, lean_mass_kg=71.8),
        ]
        rows = compute_gain_quality(results)
        self.assertAlmostEqual(rows[1].delta_fat_kg, -0.5, delta=1e-9)
        self.assertAlmostEqual(rows[1].delta_lean_kg, -0.2, delta=1e-9)
        self.assertAlmostEqual(rows[1].fat_ratio, -0.5 / -0.7, delta=1e-9)

    def test_sorts_out_of_order_input_by_date(self):
        results = [
            make_result(1, fat_mass_kg=18.2, lean_mass_kg=72.6),
            make_result(0, fat_mass_kg=18.0, lean_mass_kg=72.0),
        ]
        rows = compute_gain_quality(results)
        self.assertEqual([r.date for r in rows], sorted(r.date for r in rows))

    def test_delta_lean_plus_delta_fat_equals_weight_delta_for_a_real_series(self):
        """Ties GainQuality back to the engine's own invariant: lean_mass_kg
        + fat_mass_kg == weight_kg by construction, so delta_lean + delta_fat
        must equal weight_delta_kg for every row of a real computed series."""
        profile = ProfileParams(
            height_cm=176,
            sex=1,
            birthdate=date(2001, 8, 22),
            target_bf=0.15,
            weekly_rate=-0.005,
        )
        logs = [
            LogInput(
                date=date(2026, 6, 19),
                weight_kg=91.0,
                waist_cm=80.5,
                neck_cm=35.0,
                intake_kcal=2050.0,
                steps=5200,
            ),
            LogInput(
                date=date(2026, 6, 26),
                weight_kg=90.7,
                waist_cm=80.0,
                neck_cm=35.0,
                intake_kcal=2014.30,
                steps=5000,
            ),
        ]
        results = CompositionEngine.compute_series(profile, logs)
        rows = compute_gain_quality(results)
        for result, row in zip(results, rows):
            self.assertAlmostEqual(
                row.delta_lean_kg + row.delta_fat_kg, result.weight_delta_kg, delta=1e-6
            )


if __name__ == "__main__":
    unittest.main()
