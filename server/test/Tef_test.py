"""Phase 3.4, F9: TEF computed directly from logged macronutrient grams.
`compute_tef_breakdown` is a read-side view; each test builds the minimal
`BodyLog`-like/`CompositionResult` series it reads (see the module's
docstring for which fields those are)."""

import unittest
from dataclasses import dataclass
from datetime import date, timedelta

from server.src.services.composition.Tef import compute_tef_breakdown, compute_tef_kcal
from server.src.services.composition.models import CompositionResult, EngineConstants

BASE_DATE = date(2026, 1, 4)


@dataclass
class FakeLog:
    date: date
    cardio_kcal: float = 0.0
    carbs_g: float = None
    fat_g: float = None
    protein_g: float = None


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
        tef_kcal=240.0,
        tef_mode="flat",
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


class ComputeTefKcalTest(unittest.TestCase):
    def test_matches_the_source_docs_worked_example(self):
        """docs/composition_spec.md's F9 section: Monday's worked TEF."""
        tef = compute_tef_kcal(233.9, 90.6, 198.4, 0.300, 0.135, 1.000)
        self.assertAlmostEqual(tef, 280.80, delta=0.01)

    def test_default_kappa_defaults_match_constants(self):
        ec = EngineConstants()
        tef = compute_tef_kcal(100.0, 50.0, 100.0, ec.kappa_carbs, ec.kappa_fat, ec.kappa_protein)
        self.assertAlmostEqual(tef, 0.300 * 100.0 + 0.135 * 50.0 + 1.000 * 100.0, delta=1e-9)


class ComputeTefBreakdownTest(unittest.TestCase):
    def test_week_with_macros_gets_a_full_breakdown(self):
        logs = [FakeLog(BASE_DATE, carbs_g=200.0, fat_g=70.0, protein_g=180.0)]
        results = [make_result(0, tef_mode="macros")]
        rows = compute_tef_breakdown(logs, results)

        self.assertTrue(rows[0].has_macros)
        self.assertAlmostEqual(rows[0].carb_kcal, 0.300 * 200.0, delta=1e-9)
        self.assertAlmostEqual(rows[0].fat_kcal, 0.135 * 70.0, delta=1e-9)
        self.assertAlmostEqual(rows[0].protein_kcal, 1.000 * 180.0, delta=1e-9)
        self.assertAlmostEqual(
            rows[0].tef_kcal_macros,
            rows[0].carb_kcal + rows[0].fat_kcal + rows[0].protein_kcal,
            delta=1e-9,
        )
        self.assertEqual(rows[0].tef_mode_used, "macros")

    def test_week_without_macros_only_gets_the_flat_estimate(self):
        logs = [FakeLog(BASE_DATE)]
        results = [make_result(0, tef_mode="flat")]
        rows = compute_tef_breakdown(logs, results)

        self.assertFalse(rows[0].has_macros)
        self.assertIsNone(rows[0].carb_kcal)
        self.assertIsNone(rows[0].tef_kcal_macros)
        self.assertGreater(rows[0].tef_kcal_flat, 0.0)
        self.assertEqual(rows[0].tef_mode_used, "flat")

    def test_flat_estimate_is_always_computed_even_alongside_macros(self):
        """The flat figure is a comparison baseline, computed regardless of
        which mode the account actually applied that week."""
        logs = [FakeLog(BASE_DATE, carbs_g=200.0, fat_g=70.0, protein_g=180.0)]
        results = [make_result(0, tef_mode="macros", bmr=2000.0, neat=200.0)]
        ec = EngineConstants(tef=0.10)
        rows = compute_tef_breakdown(logs, results, ec)
        expected_flat = 0.10 * (2000.0 + 200.0 + 0.0) / (1 - 0.10)
        self.assertAlmostEqual(rows[0].tef_kcal_flat, expected_flat, delta=1e-9)

    def test_sorts_out_of_order_input_by_date(self):
        logs = [FakeLog(BASE_DATE + timedelta(days=7)), FakeLog(BASE_DATE)]
        results = [make_result(1), make_result(0)]
        rows = compute_tef_breakdown(logs, results)
        self.assertEqual([r.date for r in rows], sorted(r.date for r in rows))


if __name__ == "__main__":
    unittest.main()
