"""Phase 10.2 (Today dashboard section, see README): each test builds the
minimal `CompositionResult` (the held "latest computed week") and a
simple stand-in for today's `BodyLog` row -- `compute_today_estimate` only
reads weight_kg/intake_kcal/steps/cardio_kcal/carbs_g/fat_g/protein_g from
it (see TodayEstimate.py's `_LogLike` protocol)."""

import unittest
from dataclasses import dataclass
from datetime import date
from typing import Optional

from server.src.services.composition.models import DEFAULT_ENGINE_CONSTANTS, EngineConstants
from server.src.services.composition.TodayEstimate import compute_today_estimate
from server.test.GainQuality_test import make_result

TODAY = date(2026, 7, 10)


@dataclass
class FakeLog:
    weight_kg: Optional[float] = None
    intake_kcal: Optional[float] = None
    steps: Optional[float] = None
    cardio_kcal: float = 0.0
    carbs_g: Optional[float] = None
    fat_g: Optional[float] = None
    protein_g: Optional[float] = None


class TodayEstimateTest(unittest.TestCase):
    def test_no_log_and_no_computed_week_yields_all_unknown(self):
        row = compute_today_estimate(TODAY, None, None)
        self.assertTrue(row.is_current)
        self.assertIsNone(row.steps)
        self.assertIsNone(row.neat_kcal)
        self.assertIsNone(row.tef_kcal)
        self.assertIsNone(row.kcal_to_target)

    def test_no_log_yet_but_a_computed_history_exists(self):
        """No row for today at all -- still "current" (nothing logged
        yet), but held figures needing today's own steps/intake stay
        unknown."""
        latest = make_result(fat_mass_kg=18.0, lean_mass_kg=72.0, bmr=2100.0, target_calories=1900.0)
        row = compute_today_estimate(TODAY, None, latest)
        self.assertTrue(row.is_current)
        self.assertIsNone(row.steps)
        self.assertIsNone(row.neat_kcal)  # no steps to compute it from
        self.assertIsNone(row.kcal_to_target)  # no intake_kcal to diff against

    def test_partial_log_is_current_and_computes_available_estimates(self):
        latest = make_result(fat_mass_kg=18.0, lean_mass_kg=72.0, bmr=2100.0, target_calories=1900.0)
        today_log = FakeLog(steps=6000, intake_kcal=1800, cardio_kcal=200)
        row = compute_today_estimate(TODAY, today_log, latest, DEFAULT_ENGINE_CONSTANTS)

        self.assertTrue(row.is_current)  # no weight_kg logged today yet
        self.assertEqual(row.steps, 6000)
        self.assertEqual(row.intake_kcal, 1800)
        self.assertEqual(row.eat_kcal, 200)
        # held weight = 18 + 72 = 90kg; NEAT = 0.5 * 90 * (6000/1000) = 270
        self.assertAlmostEqual(row.neat_kcal, 270.0)
        # flat TEF = tef * (bmr + neat + eat) / (1 - tef)
        expected_tef = DEFAULT_ENGINE_CONSTANTS.tef * (2100.0 + 270.0 + 200.0) / (
            1 - DEFAULT_ENGINE_CONSTANTS.tef
        )
        self.assertAlmostEqual(row.tef_kcal, expected_tef)
        self.assertEqual(row.tef_mode, "flat")
        self.assertAlmostEqual(row.kcal_to_target, 1900.0 - 1800)

    def test_complete_log_is_no_longer_current(self):
        latest = make_result()
        today_log = FakeLog(weight_kg=90.0, steps=6000, intake_kcal=1800, cardio_kcal=0)
        row = compute_today_estimate(TODAY, today_log, latest)
        self.assertFalse(row.is_current)

    def test_macro_mode_uses_macros_when_logged(self):
        ec = EngineConstants(tef_mode="macros", kappa_carbs=0.3, kappa_fat=0.135, kappa_protein=1.0)
        latest = make_result(fat_mass_kg=18.0, lean_mass_kg=72.0, bmr=2100.0)
        today_log = FakeLog(
            steps=6000, intake_kcal=1800, cardio_kcal=100,
            carbs_g=200, fat_g=60, protein_g=150,
        )
        row = compute_today_estimate(TODAY, today_log, latest, ec)
        expected = 0.3 * 200 + 0.135 * 60 + 1.0 * 150
        self.assertAlmostEqual(row.tef_kcal, expected)
        self.assertEqual(row.tef_mode, "macros")

    def test_macro_mode_falls_back_to_flat_without_macros_logged(self):
        ec = EngineConstants(tef_mode="macros")
        latest = make_result(fat_mass_kg=18.0, lean_mass_kg=72.0, bmr=2100.0)
        today_log = FakeLog(steps=6000, intake_kcal=1800, cardio_kcal=0)
        row = compute_today_estimate(TODAY, today_log, latest, ec)
        self.assertEqual(row.tef_mode, "flat")

    def test_activity_goal_left_today(self):
        latest = make_result()
        today_log = FakeLog(steps=6000, intake_kcal=1800, cardio_kcal=100)
        row = compute_today_estimate(
            TODAY, today_log, latest, steps_goal=10000, cardio_kcal_goal=300
        )
        self.assertEqual(row.steps_left, 4000)
        self.assertEqual(row.cardio_left, 200)

    def test_no_activity_goal_leaves_left_fields_none(self):
        latest = make_result()
        today_log = FakeLog(steps=6000, intake_kcal=1800, cardio_kcal=100)
        row = compute_today_estimate(TODAY, today_log, latest)
        self.assertIsNone(row.steps_left)
        self.assertIsNone(row.cardio_left)


if __name__ == "__main__":
    unittest.main()
