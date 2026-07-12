import unittest
from datetime import date

from server.src.data.db.AuditLogDAO import AuditLogDAO
from server.src.data.db.DB import DB
from server.src.data.db.GoalPlanDAO import GoalPlanDAO
from server.src.data.db.UserDAO import UserDAO
from server.src.services.GoalPlanManager import (
    GoalPlanManager,
    GoalPlanManagerError,
    check_direction_matches_rate,
    check_goal_coherence,
)


class GoalPlanManagerTest(unittest.TestCase):
    def setUp(self):
        self.db = DB(":memory:")
        self.goal_plan_dao = GoalPlanDAO(self.db)
        self.audit_log_dao = AuditLogDAO(self.db)
        self.manager = GoalPlanManager(
            self.goal_plan_dao, audit_log_dao=self.audit_log_dao
        )
        self.user_id = UserDAO(self.db).create(
            username="demo_cut",
            email="demo_cut@example.com",
            password_hash="hash",
            height_cm=176,
            sex=1,
            birthdate=date(2001, 8, 22),
        ).user_id

    def tearDown(self):
        self.db.close()

    def test_create_goal_plan_validates_target_bf(self):
        with self.assertRaises(GoalPlanManagerError):
            self.manager.create_goal_plan(self.user_id, 1.5, -0.005, "cut")
        with self.assertRaises(GoalPlanManagerError):
            self.manager.create_goal_plan(self.user_id, 0.0, -0.005, "cut")

    def test_first_goal_plan_becomes_active(self):
        goal = self.manager.create_goal_plan(self.user_id, 0.15, -0.005, "cut")
        self.assertTrue(goal.active)
        self.assertEqual(self.manager.get_active(self.user_id).goal_id, goal.goal_id)

    def test_new_goal_plan_deactivates_the_previous_one(self):
        first = self.manager.create_goal_plan(self.user_id, 0.15, -0.005, "cut")
        second = self.manager.create_goal_plan(self.user_id, 0.18, -0.004, "cut")

        self.assertEqual(self.manager.get_active(self.user_id).goal_id, second.goal_id)
        history = self.manager.list_history(self.user_id)
        self.assertEqual(len(history), 2)
        self.assertFalse(
            next(g for g in history if g.goal_id == first.goal_id).active
        )

    def test_goal_plan_changes_are_audited(self):
        self.manager.create_goal_plan(self.user_id, 0.15, -0.005, "cut")
        self.manager.create_goal_plan(self.user_id, 0.18, -0.004, "cut")

        entries = self.audit_log_dao.list_for_user(self.user_id)
        entity_types = {entry.entity_type for entry in entries}
        self.assertEqual(entity_types, {"goal_plan"})
        # deactivate(1) + direction(2) + target_bf(2) + weekly_rate(2) = 7 entries total.
        self.assertEqual(len(entries), 7)

    # Phase 12.1: `direction` is now explicit and user-chosen, not derived
    # from weekly_rate's sign -- see docs/composition_spec.md's "Phase 12"
    # section.

    def test_create_goal_plan_stores_the_given_direction(self):
        cut = self.manager.create_goal_plan(self.user_id, 0.15, -0.005, "cut")
        self.assertEqual(cut.direction, "cut")
        bulk = self.manager.create_goal_plan(self.user_id, 0.15, 0.005, "bulk")
        self.assertEqual(bulk.direction, "bulk")

    def test_create_goal_plan_rejects_an_unknown_direction(self):
        with self.assertRaises(GoalPlanManagerError):
            self.manager.create_goal_plan(self.user_id, 0.15, -0.005, "maintain")

    def test_create_goal_plan_rejects_bulk_direction_with_a_negative_rate(self):
        with self.assertRaises(GoalPlanManagerError):
            self.manager.create_goal_plan(self.user_id, 0.15, -0.005, "bulk")

    def test_create_goal_plan_rejects_cut_direction_with_a_positive_rate(self):
        with self.assertRaises(GoalPlanManagerError):
            self.manager.create_goal_plan(self.user_id, 0.15, 0.005, "cut")

    def test_create_goal_plan_allows_any_direction_for_a_zero_rate(self):
        # The Phase 5.2 placeholder/maintenance case -- 0.0 has no sign to
        # validate direction against.
        cut = self.manager.create_goal_plan(self.user_id, 0.15, 0.0, "cut")
        self.assertEqual(cut.direction, "cut")

    def test_check_direction_matches_rate_allows_a_matching_sign(self):
        check_direction_matches_rate("cut", -0.005)
        check_direction_matches_rate("bulk", 0.005)

    def test_check_direction_matches_rate_allows_any_direction_at_zero_rate(self):
        check_direction_matches_rate("cut", 0.0)
        check_direction_matches_rate("bulk", 0.0)

    def test_check_direction_matches_rate_rejects_a_mismatched_sign(self):
        with self.assertRaises(GoalPlanManagerError):
            check_direction_matches_rate("bulk", -0.005)
        with self.assertRaises(GoalPlanManagerError):
            check_direction_matches_rate("cut", 0.005)

    def test_check_direction_matches_rate_rejects_an_unknown_direction(self):
        with self.assertRaises(GoalPlanManagerError):
            check_direction_matches_rate("maintain", -0.005)

    def test_active_period_start_is_none_with_no_goal(self):
        self.assertIsNone(self.manager.active_period_start(self.user_id))

    def test_active_period_start_is_none_for_a_never_changed_goal(self):
        # A log dated before the account's very first goal (created with
        # start_date=birthdate at registration, UserManager.register) must
        # never be spuriously excluded when the account has never actually
        # changed its goal.
        self.manager.create_goal_plan(self.user_id, 0.15, -0.005, "cut")
        self.assertIsNone(self.manager.active_period_start(self.user_id))

    def test_active_period_start_is_the_active_goal_start_date_once_changed(self):
        self.manager.create_goal_plan(
            self.user_id, 0.15, -0.005, "cut", start_date=date(2026, 1, 1)
        )
        second = self.manager.create_goal_plan(
            self.user_id, 0.18, 0.003, "bulk", start_date=date(2026, 3, 1)
        )
        self.assertEqual(self.manager.active_period_start(self.user_id), second.start_date)
        self.assertEqual(self.manager.active_period_start(self.user_id), date(2026, 3, 1))

    def test_metrics_cache_is_invalidated_on_goal_change(self):
        calls = []

        class FakeMetricsCache:
            def invalidate_for_user(self, user_id):
                calls.append(user_id)

        manager = GoalPlanManager(self.goal_plan_dao, metrics_cache=FakeMetricsCache())
        manager.create_goal_plan(self.user_id, 0.15, -0.005, "cut")
        self.assertEqual(calls, [self.user_id])

    # Phase 8.2: sign-coherence between a candidate goal and the account's
    # actual current body fat.

    # Phase 12.2 corrected the sign rule: both a cut and a bulk goal must
    # target a body fat percentage at or below the account's current one
    # (a bulk reaches it by growing lean mass, not by gaining fat) -- see
    # docs/composition_spec.md's "Phase 12" section. `weekly_rate`/
    # `direction` play no role in this check anymore.

    def test_check_goal_coherence_skips_entirely_with_no_current_bf(self):
        check_goal_coherence(None, 0.15)

    def test_check_goal_coherence_allows_a_target_at_or_below_current_bf(self):
        check_goal_coherence(0.20, 0.15)

    def test_check_goal_coherence_allows_a_target_within_epsilon_of_current(self):
        check_goal_coherence(0.20, 0.201)

    def test_check_goal_coherence_rejects_a_target_above_current_bf(self):
        with self.assertRaises(GoalPlanManagerError):
            check_goal_coherence(0.20, 0.25)

    def test_create_goal_plan_rejects_an_incoherent_goal(self):
        with self.assertRaises(GoalPlanManagerError):
            self.manager.create_goal_plan(
                self.user_id, 0.25, 0.005, "bulk", current_bf=0.20
            )

    def test_create_goal_plan_allows_a_coherent_bulk_goal(self):
        # A target below current body fat is coherent for a bulk goal too
        # (Phase 12.2) -- it used to be rejected under the pre-12.2 sign
        # rule, which required a bulk target to be at or above current.
        goal = self.manager.create_goal_plan(
            self.user_id, 0.15, 0.005, "bulk", current_bf=0.20
        )
        self.assertEqual(goal.target_bf, 0.15)

    def test_create_goal_plan_allows_a_coherent_goal(self):
        goal = self.manager.create_goal_plan(
            self.user_id, 0.15, -0.005, "cut", current_bf=0.20
        )
        self.assertEqual(goal.target_bf, 0.15)

    # Phase 8.1: retroactively editing the active goal's start_date.

    def test_update_start_date_moves_the_active_goal_in_place(self):
        goal = self.manager.create_goal_plan(
            self.user_id, 0.15, -0.005, "cut", start_date=date(2026, 3, 1)
        )
        updated = self.manager.update_start_date(self.user_id, date(2026, 1, 1))
        self.assertEqual(updated.goal_id, goal.goal_id)
        self.assertEqual(updated.start_date, date(2026, 1, 1))
        self.assertEqual(self.manager.get_active(self.user_id).start_date, date(2026, 1, 1))
        self.assertEqual(len(self.manager.list_history(self.user_id)), 1)

    def test_update_start_date_requires_an_active_goal(self):
        with self.assertRaises(GoalPlanManagerError):
            self.manager.update_start_date(self.user_id, date(2026, 1, 1))

    def test_update_start_date_rejects_a_future_date(self):
        self.manager.create_goal_plan(self.user_id, 0.15, -0.005, "cut")
        with self.assertRaises(GoalPlanManagerError):
            self.manager.update_start_date(self.user_id, date(2999, 1, 1))

    def test_update_start_date_rejects_on_or_before_the_previous_goals_start(self):
        self.manager.create_goal_plan(
            self.user_id, 0.15, -0.005, "cut", start_date=date(2026, 1, 1)
        )
        self.manager.create_goal_plan(
            self.user_id, 0.18, 0.003, "bulk", start_date=date(2026, 3, 1)
        )
        with self.assertRaises(GoalPlanManagerError):
            self.manager.update_start_date(self.user_id, date(2026, 1, 1))
        with self.assertRaises(GoalPlanManagerError):
            self.manager.update_start_date(self.user_id, date(2025, 12, 1))

    def test_update_start_date_allows_a_date_strictly_after_the_previous_goal(self):
        self.manager.create_goal_plan(
            self.user_id, 0.15, -0.005, "cut", start_date=date(2026, 1, 1)
        )
        self.manager.create_goal_plan(
            self.user_id, 0.18, 0.003, "bulk", start_date=date(2026, 3, 1)
        )
        updated = self.manager.update_start_date(self.user_id, date(2026, 1, 2))
        self.assertEqual(updated.start_date, date(2026, 1, 2))

    def test_update_start_date_is_audited(self):
        self.manager.create_goal_plan(
            self.user_id, 0.15, -0.005, "cut", start_date=date(2026, 3, 1)
        )
        self.manager.update_start_date(self.user_id, date(2026, 1, 1))
        entries = self.audit_log_dao.list_for_user(self.user_id)
        start_date_entries = [e for e in entries if e.field == "start_date"]
        self.assertEqual(len(start_date_entries), 1)
        self.assertEqual(start_date_entries[0].previous_value, "2026-03-01")
        self.assertEqual(start_date_entries[0].new_value, "2026-01-01")

    def test_update_start_date_invalidates_the_metrics_cache(self):
        calls = []

        class FakeMetricsCache:
            def invalidate_for_user(self, user_id):
                calls.append(user_id)

        manager = GoalPlanManager(self.goal_plan_dao, metrics_cache=FakeMetricsCache())
        manager.create_goal_plan(
            self.user_id, 0.15, -0.005, "cut", start_date=date(2026, 3, 1)
        )
        calls.clear()
        manager.update_start_date(self.user_id, date(2026, 1, 1))
        self.assertEqual(calls, [self.user_id])


if __name__ == "__main__":
    unittest.main()
