import unittest
from datetime import date

from server.src.data.db.AuditLogDAO import AuditLogDAO
from server.src.data.db.DB import DB
from server.src.data.db.GoalPlanDAO import GoalPlanDAO
from server.src.data.db.UserDAO import UserDAO
from server.src.services.GoalPlanManager import GoalPlanManager, GoalPlanManagerError


class GoalPlanManagerTest(unittest.TestCase):
    def setUp(self):
        self.db = DB(":memory:")
        self.goal_plan_dao = GoalPlanDAO(self.db)
        self.audit_log_dao = AuditLogDAO(self.db)
        self.manager = GoalPlanManager(
            self.goal_plan_dao, audit_log_dao=self.audit_log_dao
        )
        self.user_id = UserDAO(self.db).create(
            username="danel",
            email="danel@example.com",
            password_hash="hash",
            height_cm=176,
            sex=1,
            birthdate=date(2001, 8, 22),
        ).user_id

    def tearDown(self):
        self.db.close()

    def test_create_goal_plan_validates_target_bf(self):
        with self.assertRaises(GoalPlanManagerError):
            self.manager.create_goal_plan(self.user_id, 1.5, -0.005)
        with self.assertRaises(GoalPlanManagerError):
            self.manager.create_goal_plan(self.user_id, 0.0, -0.005)

    def test_first_goal_plan_becomes_active(self):
        goal = self.manager.create_goal_plan(self.user_id, 0.15, -0.005)
        self.assertTrue(goal.active)
        self.assertEqual(self.manager.get_active(self.user_id).goal_id, goal.goal_id)

    def test_new_goal_plan_deactivates_the_previous_one(self):
        first = self.manager.create_goal_plan(self.user_id, 0.15, -0.005)
        second = self.manager.create_goal_plan(self.user_id, 0.18, -0.004)

        self.assertEqual(self.manager.get_active(self.user_id).goal_id, second.goal_id)
        history = self.manager.list_history(self.user_id)
        self.assertEqual(len(history), 2)
        self.assertFalse(
            next(g for g in history if g.goal_id == first.goal_id).active
        )

    def test_goal_plan_changes_are_audited(self):
        self.manager.create_goal_plan(self.user_id, 0.15, -0.005)
        self.manager.create_goal_plan(self.user_id, 0.18, -0.004)

        entries = self.audit_log_dao.list_for_user(self.user_id)
        entity_types = {entry.entity_type for entry in entries}
        self.assertEqual(entity_types, {"goal_plan"})
        # deactivate(1) + target_bf(2) + weekly_rate(2) = 5 entries total.
        self.assertEqual(len(entries), 5)

    def test_metrics_cache_is_invalidated_on_goal_change(self):
        calls = []

        class FakeMetricsCache:
            def invalidate_for_user(self, user_id):
                calls.append(user_id)

        manager = GoalPlanManager(self.goal_plan_dao, metrics_cache=FakeMetricsCache())
        manager.create_goal_plan(self.user_id, 0.15, -0.005)
        self.assertEqual(calls, [self.user_id])


if __name__ == "__main__":
    unittest.main()
