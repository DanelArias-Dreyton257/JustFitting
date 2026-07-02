import unittest
from datetime import date

from server.src.data.db.DB import DB
from server.src.data.db.ProjectionDAO import ProjectionDAO
from server.src.data.db.UserDAO import UserDAO
from server.src.services.composition.models import LogInput, ProfileParams
from server.src.services.ProjectionService import ProjectionService

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


class ProjectionServiceTest(unittest.TestCase):
    def setUp(self):
        self.db = DB(":memory:")
        self.service = ProjectionService(ProjectionDAO(self.db))
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

    def test_save_run_persists_all_rows_under_one_run_id(self):
        run_id, rows = self.service.save_run(self.user_id, PROFILE, REAL_LOGS, weeks=3)
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(row.run_id == run_id for row in rows))
        self.assertTrue(all(row.base_regression == "real_only" for row in rows))
        self.assertTrue(all(row.source_model == "ols_linear" for row in rows))

    def test_get_run_and_get_latest_run_round_trip(self):
        run_id, rows = self.service.save_run(self.user_id, PROFILE, REAL_LOGS, weeks=2)

        fetched = self.service.get_run(self.user_id, run_id)
        self.assertEqual(len(fetched), 2)
        self.assertEqual([row.projection_id for row in fetched], [row.projection_id for row in rows])

        latest_run_id, latest_rows = self.service.get_latest_run(self.user_id)
        self.assertEqual(latest_run_id, run_id)
        self.assertEqual(len(latest_rows), 2)

    def test_list_runs_groups_by_run_id(self):
        self.service.save_run(self.user_id, PROFILE, REAL_LOGS, weeks=2)
        self.service.save_run(self.user_id, PROFILE, REAL_LOGS, weeks=4)

        runs = self.service.list_runs(self.user_id)
        self.assertEqual(len(runs), 2)
        self.assertEqual({run["weeks"] for run in runs}, {2, 4})

    def test_save_run_rejects_fewer_than_two_real_logs(self):
        with self.assertRaises(ValueError):
            self.service.save_run(self.user_id, PROFILE, REAL_LOGS[:1], weeks=2)


if __name__ == "__main__":
    unittest.main()
