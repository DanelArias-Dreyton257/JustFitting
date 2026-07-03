"""Alerts & feedback detectors (Phase 1.3): each test constructs the
minimal `CompositionResult` series needed to trip (or not trip) one
detector, since `Alerts.detect_alerts` only reads a handful of
already-computed fields (see Alerts.py's module docstring)."""

import unittest
from datetime import date, timedelta

from server.src.data.domain.GoalPlan import GoalPlan
from server.src.services.composition import Alerts
from server.src.services.composition.models import CompositionResult, EngineConstants

BASE_DATE = date(2026, 1, 4)


def make_goal(weekly_rate: float, **overrides) -> GoalPlan:
    defaults = dict(
        goal_id=1,
        user_id=1,
        target_bf=0.15,
        weekly_rate=weekly_rate,
        start_date=BASE_DATE,
        active=True,
        created_at=BASE_DATE,
    )
    defaults.update(overrides)
    return GoalPlan(**defaults)


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


class ImplausibleChangeAlertTest(unittest.TestCase):
    def test_flags_a_swing_above_the_threshold(self):
        results = [make_result(0), make_result(1, weight_delta_pct=0.12)]
        alerts = Alerts.detect_alerts(results)
        implausible = [a for a in alerts if a.type == "implausible_change"]
        self.assertEqual(len(implausible), 1)
        self.assertEqual(implausible[0].severity, "warning")
        self.assertEqual(implausible[0].date, results[1].date)

    def test_does_not_flag_a_normal_change(self):
        results = [make_result(0), make_result(1, weight_delta_pct=0.02)]
        alerts = Alerts.detect_alerts(results)
        self.assertFalse(any(a.type == "implausible_change" for a in alerts))

    def test_ignores_projected_rows(self):
        results = [make_result(0), make_result(1, weight_delta_pct=0.12, source="projected")]
        alerts = Alerts.detect_alerts(results)
        self.assertFalse(any(a.type == "implausible_change" for a in alerts))


class StagnationAlertTest(unittest.TestCase):
    def test_flags_three_consecutive_flat_weeks(self):
        results = [
            make_result(0, weight_delta_kg=-0.9),  # big move: breaks the first window
            make_result(1, weight_delta_kg=0.05),
            make_result(2, weight_delta_kg=-0.1),
            make_result(3, weight_delta_kg=0.05),
        ]
        alerts = Alerts.detect_alerts(results)
        stagnation = [a for a in alerts if a.type == "stagnation"]
        self.assertEqual(len(stagnation), 1)
        self.assertEqual(stagnation[0].date, results[3].date)

    def test_does_not_flag_when_one_week_moves_enough(self):
        results = [
            make_result(0, weight_delta_kg=0.0),
            make_result(1, weight_delta_kg=0.05),
            make_result(2, weight_delta_kg=-0.8),
            make_result(3, weight_delta_kg=0.05),
        ]
        alerts = Alerts.detect_alerts(results)
        self.assertFalse(any(a.type == "stagnation" for a in alerts))


class ExcessiveLeanLossAlertTest(unittest.TestCase):
    def test_flags_lean_heavy_weight_loss_over_the_window(self):
        results = [
            make_result(0, fat_mass_kg=20.0, lean_mass_kg=70.0),
            make_result(1, fat_mass_kg=19.7, lean_mass_kg=69.0),
            make_result(2, fat_mass_kg=19.4, lean_mass_kg=68.0),
            make_result(3, fat_mass_kg=19.1, lean_mass_kg=67.0),
            make_result(4, fat_mass_kg=19.0, lean_mass_kg=66.0),
        ]
        alerts = Alerts.detect_alerts(results)
        lean_loss = [a for a in alerts if a.type == "excessive_lean_loss"]
        self.assertEqual(len(lean_loss), 1)
        self.assertEqual(lean_loss[0].date, results[4].date)

    def test_does_not_flag_fat_dominant_loss(self):
        results = [
            make_result(0, fat_mass_kg=24.0, lean_mass_kg=70.0),
            make_result(1, fat_mass_kg=22.5, lean_mass_kg=69.8),
            make_result(2, fat_mass_kg=21.0, lean_mass_kg=69.6),
            make_result(3, fat_mass_kg=19.5, lean_mass_kg=69.4),
            make_result(4, fat_mass_kg=18.0, lean_mass_kg=69.2),
        ]
        alerts = Alerts.detect_alerts(results)
        self.assertFalse(any(a.type == "excessive_lean_loss" for a in alerts))

    def test_does_not_flag_a_net_gain(self):
        results = [
            make_result(0, fat_mass_kg=18.0, lean_mass_kg=70.0),
            make_result(1, fat_mass_kg=18.2, lean_mass_kg=70.2),
            make_result(2, fat_mass_kg=18.4, lean_mass_kg=70.4),
            make_result(3, fat_mass_kg=18.6, lean_mass_kg=70.6),
            make_result(4, fat_mass_kg=18.8, lean_mass_kg=70.8),
        ]
        alerts = Alerts.detect_alerts(results)
        self.assertFalse(any(a.type == "excessive_lean_loss" for a in alerts))


class DeviationAlertTest(unittest.TestCase):
    def test_flags_a_significant_gap_from_the_weekly_objective(self):
        results = [make_result(0, weight_gap_kg=1.5)]
        alerts = Alerts.detect_alerts(results)
        deviation = [a for a in alerts if a.type == "deviation"]
        self.assertEqual(len(deviation), 1)
        self.assertEqual(deviation[0].severity, "info")

    def test_does_not_flag_a_small_gap(self):
        results = [make_result(0, weight_gap_kg=0.2)]
        alerts = Alerts.detect_alerts(results)
        self.assertFalse(any(a.type == "deviation" for a in alerts))


class DetectAlertsOrderingTest(unittest.TestCase):
    def test_alerts_are_sorted_by_date(self):
        results = [
            make_result(0, weight_gap_kg=2.0),
            make_result(1, weight_delta_pct=0.15),
        ]
        # Feed them out of order; detect_alerts must sort internally.
        alerts = Alerts.detect_alerts(list(reversed(results)))
        dates = [a.date for a in alerts]
        self.assertEqual(dates, sorted(dates))


class CustomThresholdsTest(unittest.TestCase):
    """Phase 1.5: per-user alert thresholds. Omitting `thresholds` must
    reproduce today's fixed `constants.py` behavior (the other test classes
    above already pin that); this covers that an override actually shifts
    the detection boundary."""

    def test_tighter_deviation_threshold_flags_a_gap_the_default_would_not(self):
        results = [make_result(0, weight_gap_kg=0.5)]
        default_alerts = Alerts.detect_alerts(results)
        self.assertFalse(any(a.type == "deviation" for a in default_alerts))

        tighter = Alerts.detect_alerts(
            results, EngineConstants(significant_deviation_kg=0.3)
        )
        self.assertTrue(any(a.type == "deviation" for a in tighter))

    def test_shorter_stagnation_window_flags_two_flat_weeks(self):
        results = [
            make_result(0, weight_delta_kg=0.0),
            make_result(1, weight_delta_kg=0.05),
        ]
        default_alerts = Alerts.detect_alerts(results)
        self.assertFalse(any(a.type == "stagnation" for a in default_alerts))

        shorter_window = Alerts.detect_alerts(
            results, EngineConstants(stagnation_weeks=2)
        )
        self.assertTrue(any(a.type == "stagnation" for a in shorter_window))


class BulkRateAlertTest(unittest.TestCase):
    """Phase 3, F1: a bulk goal's weekly rate outside the recommended
    [0.25%, 0.5%] range is flagged (not blocked)."""

    def test_in_range_bulk_rate_is_not_flagged(self):
        results = [make_result(0)]
        alerts = Alerts.detect_alerts(results, goal=make_goal(0.003))
        self.assertFalse(any(a.type == "bulk_rate_out_of_range" for a in alerts))

    def test_below_range_bulk_rate_is_flagged(self):
        results = [make_result(0)]
        alerts = Alerts.detect_alerts(results, goal=make_goal(0.001))
        flagged = [a for a in alerts if a.type == "bulk_rate_out_of_range"]
        self.assertEqual(len(flagged), 1)
        self.assertEqual(flagged[0].severity, "info")

    def test_above_range_bulk_rate_is_flagged(self):
        results = [make_result(0)]
        alerts = Alerts.detect_alerts(results, goal=make_goal(0.01))
        self.assertTrue(any(a.type == "bulk_rate_out_of_range" for a in alerts))

    def test_cut_direction_is_never_flagged_regardless_of_rate(self):
        results = [make_result(0)]
        alerts = Alerts.detect_alerts(results, goal=make_goal(-0.01))
        self.assertFalse(any(a.type == "bulk_rate_out_of_range" for a in alerts))

    def test_no_goal_is_never_flagged(self):
        results = [make_result(0)]
        alerts = Alerts.detect_alerts(results, goal=None)
        self.assertFalse(any(a.type == "bulk_rate_out_of_range" for a in alerts))


if __name__ == "__main__":
    unittest.main()
