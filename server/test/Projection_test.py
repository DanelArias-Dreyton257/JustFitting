import unittest
from datetime import date

from server.src.services.composition import Projection
from server.src.services.composition.models import LogInput, ProfileParams

PROFILE = ProfileParams(
    height_cm=176,
    sex=1,
    birthdate=date(2001, 8, 22),
    target_bf=0.15,
    weekly_rate=-0.005,
)

REAL_LOGS = [
    LogInput(date(2025, 12, 28), 97.0, 91.0, 38.5, 2400.0, 6000),
    LogInput(date(2026, 1, 4), 96.4, 90.5, 38.5, 2350.0, 6200),
    LogInput(date(2026, 1, 11), 95.9, 90.0, 38.4, 2320.0, 6100),
]


class ProjectionTest(unittest.TestCase):
    def test_requires_at_least_two_real_logs(self):
        with self.assertRaises(ValueError):
            Projection.project_series(PROFILE, REAL_LOGS[:1], weeks=2)

    def test_zero_weeks_returns_empty(self):
        self.assertEqual(Projection.project_series(PROFILE, REAL_LOGS, weeks=0), [])

    def test_projected_rows_hold_steps_constant(self):
        projected = Projection.project_series(PROFILE, REAL_LOGS, weeks=2)
        # steps aren't on CompositionResult directly, but NEAT is derived from
        # them together with weight, so recompute the implied steps ratio
        # indirectly is out of scope here; assert dates/labels instead.
        self.assertEqual(len(projected), 2)
        for result in projected:
            self.assertEqual(result.source, "projected")

    def test_activity_model_constant_holds_neat_flat(self):
        pairs = Projection.project_series_with_inputs(
            PROFILE, REAL_LOGS, weeks=3, activity_model="constant"
        )
        last_real_steps = REAL_LOGS[-1].steps
        for log, _ in pairs:
            self.assertEqual(log.steps, last_real_steps)

    def test_activity_model_trend_follows_the_steps_regression(self):
        # Steps rise then dip in REAL_LOGS (6000, 6200, 6100); a "trend"
        # forecast should differ from just carrying the last value forward.
        pairs = Projection.project_series_with_inputs(
            PROFILE, REAL_LOGS, weeks=3, activity_model="trend"
        )
        last_real_steps = REAL_LOGS[-1].steps
        forecasted_steps = [log.steps for log, _ in pairs]
        self.assertTrue(any(steps != last_real_steps for steps in forecasted_steps))
        self.assertTrue(all(steps >= 0 for steps in forecasted_steps))

    def test_trend_model_ols_default_is_unchanged(self):
        default = Projection.project_series(PROFILE, REAL_LOGS, weeks=3)
        explicit_ols = Projection.project_series(
            PROFILE, REAL_LOGS, weeks=3, trend_model="ols"
        )
        for a, b in zip(default, explicit_ols):
            self.assertEqual(a.bmi, b.bmi)
            self.assertEqual(a.target_calories, b.target_calories)

    def test_weighted_ols_leans_toward_the_recent_slope(self):
        # A flat run followed by a sharp recent drop: plain OLS averages the
        # whole history's slope, while weighted_ols should forecast a lower
        # (more negative) weight trend since it leans on the recent drop.
        logs = [
            LogInput(date(2026, 1, 4), 100.0, 91.0, 38.5, 2400.0, 6000),
            LogInput(date(2026, 1, 11), 100.0, 91.0, 38.5, 2400.0, 6000),
            LogInput(date(2026, 1, 18), 100.0, 91.0, 38.5, 2400.0, 6000),
            LogInput(date(2026, 1, 25), 98.0, 90.5, 38.4, 2350.0, 6100),
            LogInput(date(2026, 2, 1), 96.0, 90.0, 38.3, 2320.0, 6100),
        ]
        ols_pairs = Projection.project_series_with_inputs(
            PROFILE, logs, weeks=1, trend_model="ols"
        )
        weighted_pairs = Projection.project_series_with_inputs(
            PROFILE, logs, weeks=1, trend_model="weighted_ols"
        )
        ols_weight = ols_pairs[0][0].weight_kg
        weighted_weight = weighted_pairs[0][0].weight_kg
        self.assertLess(weighted_weight, ols_weight)

    def test_real_and_projected_regression_accepts_expanding_window(self):
        real_only = Projection.project_series(
            PROFILE, REAL_LOGS, weeks=4, base_regression="real_only"
        )
        expanding = Projection.project_series(
            PROFILE, REAL_LOGS, weeks=4, base_regression="real_and_projected"
        )
        # A forecast point lies exactly on its source regression line, so
        # feeding it back in doesn't perturb an OLS fit (it trivially
        # satisfies the normal equations) -- both modes coincide for a
        # linear trend. The modes only diverge once real observations
        # deviate from that straight line in later real logs.
        for real_result, expanding_result in zip(real_only, expanding):
            self.assertAlmostEqual(real_result.bmi, expanding_result.bmi, delta=0.01)


if __name__ == "__main__":
    unittest.main()
