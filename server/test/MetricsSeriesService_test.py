"""Phase 5.3: MetricsSeriesService.compute_series_for_user scopes the
derived series to the active goal's own period once an account has
actually changed its goal -- see GoalPlanManager.active_period_start's
docstring for why a never-changed goal is a deliberate no-op regardless of
how far back a log is dated.
"""

import unittest
from datetime import date

from server.src.api.app import create_app
from server.src.services.MetricsSeriesService import compute_series_for_user


class MetricsSeriesServiceTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app({"DB_PATH": ":memory:", "TESTING": True})
        self.user_manager = self.app.extensions["user_manager"]
        self.log_manager = self.app.extensions["log_manager"]
        self.measurement_manager = self.app.extensions["body_measurement_manager"]
        self.goal_plan_manager = self.app.extensions["goal_plan_manager"]
        profile = self.user_manager.register(
            username="demo_cut",
            email="demo_cut@example.com",
            password="s3cret123",
            height_cm=176,
            sex=1,
            birthdate=date(2001, 8, 22),
            target_bf=0.15,
            weekly_rate=-0.005,
        )
        self.user_id = profile.user_id

    def tearDown(self):
        self.app.extensions["db"].close()

    def _log(self, log_date, waist_cm=90.0, neck_cm=38.0, **overrides):
        # Phase 9.1: waist/neck are a separate, sporadically-logged
        # body_measurements row -- seed one at the same date by default so a
        # `_log()`-created row is computable end-to-end, unless a caller
        # deliberately wants a still-partial one (see the partial-log tests
        # below, which skip this).
        if waist_cm is not None or neck_cm is not None:
            self.measurement_manager.create(
                self.user_id, log_date, waist_cm=waist_cm, neck_cm=neck_cm
            )
        defaults = dict(
            user_id=self.user_id,
            log_date=log_date,
            weight_kg=90.0,
            intake_kcal=2200.0,
            steps=6000,
        )
        defaults.update(overrides)
        return self.log_manager.create_log(**defaults)

    def test_never_changed_goal_includes_every_log_regardless_of_date(self):
        # The account's only-ever goal was created "today" at registration
        # -- a log dated years earlier must still be included, since
        # there's no other goal period to exclude it from.
        self._log(date(2020, 1, 1))
        self._log(date(2020, 1, 8))

        logs, results = compute_series_for_user(self.app, self.user_id)
        self.assertEqual(len(logs), 2)
        self.assertEqual(len(results), 2)

    def test_goal_change_excludes_logs_from_before_the_change(self):
        self._log(date(2026, 1, 1))
        self._log(date(2026, 1, 8))
        self.goal_plan_manager.create_goal_plan(
            self.user_id, 0.18, 0.003, "bulk", start_date=date(2026, 3, 1)
        )
        self._log(date(2026, 3, 8))
        self._log(date(2026, 3, 15))

        logs, results = compute_series_for_user(self.app, self.user_id)
        self.assertEqual([log.date for log in logs], [date(2026, 3, 8), date(2026, 3, 15)])
        self.assertEqual(len(results), 2)

    def test_log_on_the_exact_start_date_is_included(self):
        self.goal_plan_manager.create_goal_plan(
            self.user_id, 0.18, 0.003, "bulk", start_date=date(2026, 3, 1)
        )
        self._log(date(2026, 3, 1))

        logs, _ = compute_series_for_user(self.app, self.user_id)
        self.assertEqual(len(logs), 1)

    def test_all_logs_before_the_goal_change_returns_an_empty_series(self):
        self._log(date(2026, 1, 1))
        self.goal_plan_manager.create_goal_plan(
            self.user_id, 0.18, 0.003, "bulk", start_date=date(2026, 3, 1)
        )

        logs, results = compute_series_for_user(self.app, self.user_id)
        self.assertEqual(logs, [])
        self.assertEqual(results, [])

    def test_a_partial_log_is_excluded_from_the_computed_series(self):
        """Phase 7.4 (partial logs, see README): a row missing weight is
        logged, but not yet computable -- it's excluded from the series
        exactly like an unlogged week, not just silently given garbage
        numbers."""
        self._log(date(2026, 1, 1))  # complete
        self.log_manager.create_log(
            user_id=self.user_id, log_date=date(2026, 1, 8), steps=6500, intake_kcal=2100.0
        )  # partial: no weight

        logs, results = compute_series_for_user(self.app, self.user_id)
        self.assertEqual([log.date for log in logs], [date(2026, 1, 1)])
        self.assertEqual(len(results), 1)

    def test_completing_a_partial_log_makes_it_appear_in_the_series(self):
        partial = self.log_manager.create_log(
            user_id=self.user_id, log_date=date(2026, 1, 1), steps=6500, intake_kcal=2100.0
        )
        logs, results = compute_series_for_user(self.app, self.user_id)
        self.assertEqual(logs, [])

        self.log_manager.update_log(partial.log_id, weight_kg=90.0)
        logs, results = compute_series_for_user(self.app, self.user_id)
        # Still not computable -- weight is filled in, but no body_measurements
        # row has ever been logged for this account, so waist/neck can't
        # resolve yet (Phase 9.1).
        self.assertEqual(logs, [])

        self.measurement_manager.create(self.user_id, date(2026, 1, 1), waist_cm=90.0, neck_cm=38.0)
        logs, results = compute_series_for_user(self.app, self.user_id)
        self.assertEqual([log.date for log in logs], [date(2026, 1, 1)])
        self.assertEqual(len(results), 1)

    def test_a_sporadic_measurement_stays_effective_for_later_weight_only_weeks(self):
        """Phase 9.1: waist/neck are "static" from one body_measurements row
        to the next -- a week with no measurement of its own still resolves
        to the most recent prior one."""
        self._log(date(2026, 1, 1), waist_cm=91.0, neck_cm=38.5)
        # No new measurement logged for this later week -- just weight/
        # intake/steps, the same "weight logged weekly, perimeters
        # sporadically" split the feature is built around.
        self.log_manager.create_log(
            user_id=self.user_id,
            log_date=date(2026, 2, 1),
            weight_kg=89.0,
            intake_kcal=2150.0,
            steps=6100,
        )

        logs, results = compute_series_for_user(self.app, self.user_id)
        self.assertEqual([log.date for log in logs], [date(2026, 1, 1), date(2026, 2, 1)])
        self.assertEqual(len(results), 2)
        # Both weeks compute RFM/Navy from the same (91.0, 38.5) measurement.
        self.assertEqual(results[0].rfm, results[1].rfm)


if __name__ == "__main__":
    unittest.main()
