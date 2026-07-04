"""Phase 3.4 extension: evidence-based per-kg macro targets (protein/fat
direct, carbs as the remainder of target_calories). Each test builds the
minimal `BodyLog`-like/`CompositionResult` series `compute_macro_targets`
reads (see the module's docstring)."""

import unittest
from dataclasses import dataclass
from datetime import date, timedelta

from server.src.services.composition.MacroTargets import compute_macro_targets
from server.src.services.composition.models import CompositionResult, EngineConstants

BASE_DATE = date(2026, 1, 4)


@dataclass
class FakeLog:
    date: date
    weight_kg: float
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
        target_calories=2200.0,
        intake_diff=0.0,
        tef_kcal=220.0,
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


class ComputeMacroTargetsTest(unittest.TestCase):
    def test_targets_scale_with_weight_and_use_default_g_per_kg(self):
        logs = [FakeLog(BASE_DATE, weight_kg=90.0)]
        results = [make_result(0, target_calories=2200.0)]
        rows = compute_macro_targets(logs, results)

        ec = EngineConstants()
        self.assertAlmostEqual(rows[0].protein_target_g, ec.protein_target_g_per_kg * 90.0)
        self.assertAlmostEqual(rows[0].fat_target_g, ec.fat_target_g_per_kg * 90.0)
        self.assertAlmostEqual(rows[0].protein_target_kcal, rows[0].protein_target_g * 4.0)
        self.assertAlmostEqual(rows[0].fat_target_kcal, rows[0].fat_target_g * 9.0)

    def test_carbs_are_the_remainder_of_target_calories(self):
        logs = [FakeLog(BASE_DATE, weight_kg=90.0)]
        results = [make_result(0, target_calories=2200.0)]
        rows = compute_macro_targets(logs, results)
        row = rows[0]
        self.assertAlmostEqual(
            row.carbs_target_kcal,
            2200.0 - row.protein_target_kcal - row.fat_target_kcal,
            delta=1e-9,
        )
        self.assertAlmostEqual(row.carbs_target_g, row.carbs_target_kcal / 4.0, delta=1e-9)

    def test_carbs_never_go_negative_when_protein_and_fat_exceed_calories(self):
        logs = [FakeLog(BASE_DATE, weight_kg=200.0)]  # deliberately huge to force overshoot
        results = [make_result(0, target_calories=100.0)]
        rows = compute_macro_targets(logs, results)
        self.assertEqual(rows[0].carbs_target_kcal, 0.0)
        self.assertEqual(rows[0].carbs_target_g, 0.0)

    def test_no_macros_logged_reports_no_actual(self):
        logs = [FakeLog(BASE_DATE, weight_kg=90.0)]
        results = [make_result(0)]
        rows = compute_macro_targets(logs, results)
        self.assertFalse(rows[0].has_actual)
        self.assertIsNone(rows[0].protein_actual_kcal)

    def test_macros_logged_computes_actual_kcal(self):
        logs = [FakeLog(BASE_DATE, weight_kg=90.0, carbs_g=200.0, fat_g=70.0, protein_g=150.0)]
        results = [make_result(0)]
        rows = compute_macro_targets(logs, results)
        row = rows[0]
        self.assertTrue(row.has_actual)
        self.assertAlmostEqual(row.protein_actual_kcal, 150.0 * 4.0)
        self.assertAlmostEqual(row.fat_actual_kcal, 70.0 * 9.0)
        self.assertAlmostEqual(row.carbs_actual_kcal, 200.0 * 4.0)

    def test_custom_g_per_kg_overrides_change_targets(self):
        logs = [FakeLog(BASE_DATE, weight_kg=90.0)]
        results = [make_result(0)]
        ec = EngineConstants(protein_target_g_per_kg=2.0, fat_target_g_per_kg=1.0)
        rows = compute_macro_targets(logs, results, ec)
        self.assertAlmostEqual(rows[0].protein_target_g, 180.0)
        self.assertAlmostEqual(rows[0].fat_target_g, 90.0)

    def test_sorts_out_of_order_input_by_date(self):
        logs = [
            FakeLog(BASE_DATE + timedelta(days=7), weight_kg=90.0),
            FakeLog(BASE_DATE, weight_kg=90.0),
        ]
        results = [make_result(1), make_result(0)]
        rows = compute_macro_targets(logs, results)
        self.assertEqual([r.date for r in rows], sorted(r.date for r in rows))


if __name__ == "__main__":
    unittest.main()
