"""Seeding the demo accounts (Danel/cut, Sergio/bulk) -- see
docs/composition_spec.md's worked examples and services/DemoSeeder.py."""

import unittest
from datetime import date

from server.src.data.db.BodyLogDAO import BodyLogDAO
from server.src.data.db.DB import DB
from server.src.data.db.EngineSettingsDAO import EngineSettingsDAO
from server.src.data.db.GoalPlanDAO import GoalPlanDAO
from server.src.data.db.UserDAO import UserDAO
from server.src.services import DemoSeeder
from server.src.services.EngineSettingsManager import EngineSettingsManager
from server.src.services.GoalPlanManager import GoalPlanManager
from server.src.services.LogManager import LogManager
from server.src.services.UserManager import UserManager


class DemoSeederTest(unittest.TestCase):
    def setUp(self):
        self.db = DB(":memory:")
        self.goal_plan_manager = GoalPlanManager(GoalPlanDAO(self.db))
        self.user_manager = UserManager(UserDAO(self.db), self.goal_plan_manager)
        self.log_manager = LogManager(BodyLogDAO(self.db))
        self.engine_settings_manager = EngineSettingsManager(EngineSettingsDAO(self.db))

    def tearDown(self):
        self.db.close()

    def test_seeds_both_accounts(self):
        seeded = DemoSeeder.seed_if_empty(
            self.user_manager, self.log_manager, self.engine_settings_manager
        )
        self.assertTrue(seeded)
        self.assertIsNotNone(self.user_manager.user_dao.get_by_username("admin_cut"))
        self.assertIsNotNone(self.user_manager.user_dao.get_by_username("admin_bulk"))

    def test_is_idempotent(self):
        DemoSeeder.seed_if_empty(
            self.user_manager, self.log_manager, self.engine_settings_manager
        )
        seeded_again = DemoSeeder.seed_if_empty(
            self.user_manager, self.log_manager, self.engine_settings_manager
        )
        self.assertFalse(seeded_again)

    def test_cut_account_matches_the_danel_profile_and_has_default_settings(self):
        DemoSeeder.seed_if_empty(
            self.user_manager, self.log_manager, self.engine_settings_manager
        )
        cut = self.user_manager.user_dao.get_by_username("admin_cut")
        self.assertEqual(cut.height_cm, 176)
        self.assertEqual(cut.sex, 1)
        self.assertEqual(cut.birthdate, date(2001, 8, 22))

        goal = self.goal_plan_manager.get_active(cut.user_id)
        self.assertAlmostEqual(goal.target_bf, 0.15)
        self.assertAlmostEqual(goal.weekly_rate, -0.005)
        self.assertEqual(goal.direction, "cut")

        logs = self.log_manager.list_logs(cut.user_id)
        self.assertGreater(len(logs), 0)
        self.assertTrue(all(log.granularity == "weekly" for log in logs))

        self.assertIsNone(self.engine_settings_manager.get_active(cut.user_id))

    def test_bulk_account_matches_the_sergio_profile_and_gets_customized_settings(self):
        DemoSeeder.seed_if_empty(
            self.user_manager, self.log_manager, self.engine_settings_manager
        )
        bulk = self.user_manager.user_dao.get_by_username("admin_bulk")
        self.assertEqual(bulk.height_cm, 194)
        self.assertEqual(bulk.sex, 1)
        self.assertEqual(bulk.birthdate, date(2001, 4, 5))

        goal = self.goal_plan_manager.get_active(bulk.user_id)
        self.assertAlmostEqual(goal.target_bf, 0.15)
        self.assertAlmostEqual(goal.weekly_rate, 0.005)
        self.assertEqual(goal.direction, "bulk")

        settings = self.engine_settings_manager.get_active(bulk.user_id)
        self.assertIsNotNone(settings)
        self.assertEqual(settings.bmr_model, "mifflin")
        self.assertEqual(settings.tef_mode, "macros")

    def test_bulk_account_series_mixes_granularity_and_logs_macros(self):
        DemoSeeder.seed_if_empty(
            self.user_manager, self.log_manager, self.engine_settings_manager
        )
        bulk = self.user_manager.user_dao.get_by_username("admin_bulk")
        logs = self.log_manager.list_logs(bulk.user_id)

        weekly_logs = [log for log in logs if log.granularity == "weekly"]
        daily_logs = [log for log in logs if log.granularity == "daily"]
        self.assertGreater(len(weekly_logs), 0)
        self.assertGreater(len(daily_logs), 0)

        macro_logs = [log for log in daily_logs if log.carbs_g is not None]
        self.assertEqual(len(macro_logs), len(daily_logs))
        for log in macro_logs:
            self.assertIsNotNone(log.fat_g)
            self.assertIsNotNone(log.protein_g)

    def test_seed_if_empty_works_without_an_engine_settings_manager(self):
        """Backward-compatible: omitting engine_settings_manager still
        seeds both accounts, just without the bulk account's customization."""
        seeded = DemoSeeder.seed_if_empty(self.user_manager, self.log_manager)
        self.assertTrue(seeded)
        self.assertIsNotNone(self.user_manager.user_dao.get_by_username("admin_bulk"))


if __name__ == "__main__":
    unittest.main()
