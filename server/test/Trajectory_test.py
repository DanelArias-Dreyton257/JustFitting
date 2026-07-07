import unittest

from server.src.services.composition import Trajectory


class TrajectoryTest(unittest.TestCase):
    def test_base_case_has_no_predecessor(self):
        self.assertEqual(Trajectory.compute_weight_delta(97.0, None), 0.0)
        self.assertEqual(Trajectory.compute_weight_delta_pct(97.0, None), 0.0)
        self.assertEqual(Trajectory.compute_weight_objective(97.0, None, -0.005), 97.0)
        self.assertEqual(Trajectory.compute_weight_to_shed(None, 97.0), 0.0)

    def test_weight_objective_and_gap(self):
        wobj = Trajectory.compute_weight_objective(90.7, 91.0, -0.005)
        self.assertAlmostEqual(wobj, 90.545, delta=0.001)
        gap = Trajectory.compute_weight_gap(90.7, wobj)
        self.assertAlmostEqual(gap, 0.155, delta=0.001)

    def test_weight_to_shed_and_deficits(self):
        wobj = 90.545
        pi = Trajectory.compute_weight_to_shed(91.0, wobj)
        self.assertAlmostEqual(pi, 0.455, delta=0.001)
        weekly = Trajectory.compute_weekly_deficit(pi)
        self.assertAlmostEqual(weekly, 3503.5, delta=0.1)
        daily = Trajectory.compute_daily_deficit(weekly)
        self.assertAlmostEqual(daily, 500.5, delta=0.01)

    def test_final_weight_and_weeks_to_goal(self):
        final_weight = Trajectory.compute_final_weight(72.64, 0.15)
        self.assertAlmostEqual(final_weight, 85.459, delta=0.01)
        weeks = Trajectory.compute_weeks_to_goal(90.7, final_weight, -0.005)
        self.assertAlmostEqual(weeks, 11.93, delta=0.01)

    def test_weeks_to_goal_handles_a_zero_weekly_rate_without_dividing_by_zero(self):
        # ln(1 - 0) == 0 would otherwise raise ZeroDivisionError -- reachable
        # today by manually setting weekly_rate=0 (nothing validates it) and,
        # since Phase 5.2, the default for every brand-new account.
        self.assertEqual(Trajectory.compute_weeks_to_goal(90.0, 85.0, 0.0), 0.0)


if __name__ == "__main__":
    unittest.main()
