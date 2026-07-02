"""Golden acceptance test for the composition engine (see docs/composition_spec.md).

Reference profile: H=176, sex=1 (male), birthdate=2001-08-22, target_bf=0.15,
weekly_rate=-0.005. Values are checked against the verified "Danel" reference
with a tolerance of +/-0.01 (+/-0.5 kcal for calorie figures).
"""

import unittest
from datetime import date

from server.src.services.composition import CompositionEngine, Projection
from server.src.services.composition.models import LogInput, ProfileParams

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


if __name__ == "__main__":
    unittest.main()
