"""Real-increment analytics (Phase 3.2, F7): each test builds the minimal
`CompositionResult` series needed, since
`IncrementAnalytics.compute_increment_analytics` only reads
`weight_delta_pct`/`source`/`date` from each row."""

import unittest
from datetime import date, timedelta

from server.src.services.composition.IncrementAnalytics import (
    compute_increment_analytics,
)
from server.src.services.composition.models import CompositionResult

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


class IncrementAnalyticsTest(unittest.TestCase):
    def test_first_real_row_is_skipped_as_the_base_case(self):
        results = [make_result(0, weight_delta_pct=0.0)]
        rows = compute_increment_analytics(results, weekly_rate=-0.005)
        self.assertEqual(rows, [])

    def test_computes_incr_real_and_running_mean(self):
        results = [
            make_result(0, weight_delta_pct=0.0),
            make_result(1, weight_delta_pct=-0.003),
            make_result(2, weight_delta_pct=-0.007),
        ]
        rows = compute_increment_analytics(results, weekly_rate=-0.005)
        self.assertEqual(len(rows), 2)
        self.assertAlmostEqual(rows[0].incr_real_pct, -0.003, delta=1e-9)
        self.assertAlmostEqual(rows[0].incr_real_mean_pct, -0.003, delta=1e-9)
        self.assertAlmostEqual(rows[1].incr_real_pct, -0.007, delta=1e-9)
        self.assertAlmostEqual(rows[1].incr_real_mean_pct, (-0.003 + -0.007) / 2, delta=1e-9)

    def test_deviation_is_zero_when_on_target(self):
        results = [
            make_result(0, weight_delta_pct=0.0),
            make_result(1, weight_delta_pct=-0.005),
        ]
        rows = compute_increment_analytics(results, weekly_rate=-0.005)
        self.assertAlmostEqual(rows[0].deviation_pct, 0.0, delta=1e-9)

    def test_deviation_is_positive_when_undershooting_the_goal(self):
        # rho=-0.005 (target loss), actual is only -0.002 (undershot).
        results = [
            make_result(0, weight_delta_pct=0.0),
            make_result(1, weight_delta_pct=-0.002),
        ]
        rows = compute_increment_analytics(results, weekly_rate=-0.005)
        self.assertGreater(rows[0].deviation_pct, 0.0)

    def test_deviation_is_negative_when_overshooting_the_goal(self):
        results = [
            make_result(0, weight_delta_pct=0.0),
            make_result(1, weight_delta_pct=-0.01),
        ]
        rows = compute_increment_analytics(results, weekly_rate=-0.005)
        self.assertLess(rows[0].deviation_pct, 0.0)

    def test_deviation_is_none_for_a_zero_goal_rate(self):
        results = [
            make_result(0, weight_delta_pct=0.0),
            make_result(1, weight_delta_pct=0.001),
        ]
        rows = compute_increment_analytics(results, weekly_rate=0.0)
        self.assertIsNone(rows[0].deviation_pct)

    def test_ignores_projected_rows(self):
        results = [
            make_result(0, weight_delta_pct=0.0),
            make_result(1, weight_delta_pct=-0.003),
            make_result(2, weight_delta_pct=-0.05, source="projected"),
        ]
        rows = compute_increment_analytics(results, weekly_rate=-0.005)
        self.assertEqual(len(rows), 1)

    def test_sorts_out_of_order_input_by_date(self):
        results = [
            make_result(1, weight_delta_pct=-0.003),
            make_result(0, weight_delta_pct=0.0),
        ]
        rows = compute_increment_analytics(results, weekly_rate=-0.005)
        self.assertEqual([r.date for r in rows], sorted(r.date for r in rows))


if __name__ == "__main__":
    unittest.main()
