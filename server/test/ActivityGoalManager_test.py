import unittest
from datetime import date

from server.src.data.db.ActivityGoalDAO import ActivityGoalDAO
from server.src.data.db.AuditLogDAO import AuditLogDAO
from server.src.data.db.DB import DB
from server.src.data.db.UserDAO import UserDAO
from server.src.services.ActivityGoalManager import (
    ActivityGoalManager,
    ActivityGoalManagerError,
)


class ActivityGoalManagerTest(unittest.TestCase):
    def setUp(self):
        self.db = DB(":memory:")
        self.audit_log_dao = AuditLogDAO(self.db)
        self.manager = ActivityGoalManager(
            ActivityGoalDAO(self.db), audit_log_dao=self.audit_log_dao
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

    def test_no_goal_by_default(self):
        """Phase 5.2's "don't force a goal at signup" precedent applies here
        too -- unlike the main GoalPlan, a brand-new account has no
        activity goal at all until it sets one."""
        self.assertIsNone(self.manager.get_active(self.user_id))
        self.assertEqual(self.manager.list_history(self.user_id), [])

    def test_set_goal_requires_at_least_one_field(self):
        with self.assertRaises(ActivityGoalManagerError):
            self.manager.set_goal(self.user_id)

    def test_set_goal_rejects_non_positive_values(self):
        with self.assertRaises(ActivityGoalManagerError):
            self.manager.set_goal(self.user_id, steps_goal=0)
        with self.assertRaises(ActivityGoalManagerError):
            self.manager.set_goal(self.user_id, cardio_kcal_goal=-100)

    def test_set_goal_steps_only(self):
        goal = self.manager.set_goal(self.user_id, steps_goal=10000)
        self.assertEqual(goal.steps_goal, 10000)
        self.assertIsNone(goal.cardio_kcal_goal)
        self.assertTrue(goal.active)

    def test_updating_deactivates_previous_and_historizes(self):
        first = self.manager.set_goal(self.user_id, steps_goal=8000)
        second = self.manager.set_goal(self.user_id, steps_goal=10000, cardio_kcal_goal=300)

        active = self.manager.get_active(self.user_id)
        self.assertEqual(active.activity_goal_id, second.activity_goal_id)

        history = self.manager.list_history(self.user_id)
        self.assertEqual(
            [g.activity_goal_id for g in history],
            [second.activity_goal_id, first.activity_goal_id],
        )
        self.assertFalse(
            next(g for g in history if g.activity_goal_id == first.activity_goal_id).active
        )

    def test_audit_log_records_the_change(self):
        self.manager.set_goal(self.user_id, steps_goal=8000)
        entries = self.audit_log_dao.list_for_user(self.user_id)
        fields = {entry.field for entry in entries}
        self.assertIn("steps_goal", fields)
        self.assertIn("cardio_kcal_goal", fields)


if __name__ == "__main__":
    unittest.main()
