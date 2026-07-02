import unittest
from datetime import date

from server.src.data.db.BodyLogDAO import BodyLogDAO
from server.src.data.db.DB import DB
from server.src.data.db.MetricsSnapshotDAO import MetricsSnapshotDAO
from server.src.data.db.UserDAO import UserDAO
from server.src.services.composition import CompositionEngine
from server.src.services.composition.models import ProfileParams
from server.src.services.LogManager import LogManager
from server.src.services.MetricsCache import MetricsCache

PROFILE = ProfileParams(
    height_cm=176,
    sex=1,
    birthdate=date(2001, 8, 22),
    target_bf=0.15,
    weekly_rate=-0.005,
)


class MetricsCacheTest(unittest.TestCase):
    def setUp(self):
        self.db = DB(":memory:")
        self.snapshot_dao = MetricsSnapshotDAO(self.db)
        self.cache = MetricsCache(self.snapshot_dao)
        self.log_manager = LogManager(BodyLogDAO(self.db), metrics_cache=self.cache)
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

    def _seed_two_logs(self):
        self.log_manager.create_log(
            user_id=self.user_id,
            log_date=date(2025, 12, 28),
            weight_kg=97.0,
            waist_cm=91.0,
            neck_cm=38.5,
            intake_kcal=2400.0,
            steps=6000,
        )
        self.log_manager.create_log(
            user_id=self.user_id,
            log_date=date(2026, 1, 4),
            weight_kg=96.4,
            waist_cm=90.5,
            neck_cm=38.5,
            intake_kcal=2350.0,
            steps=6200,
        )

    def test_cache_miss_computes_and_stores_snapshots(self):
        self._seed_two_logs()
        logs = self.log_manager.list_logs(self.user_id)
        engine_inputs = self.log_manager.to_engine_inputs(logs)

        results = self.cache.get_or_compute_series(PROFILE, logs, engine_inputs)
        self.assertEqual(len(results), 2)
        for log in logs:
            self.assertIsNotNone(
                self.snapshot_dao.get(log.log_id, CompositionEngine.ENGINE_VERSION)
            )

    def test_cache_hit_returns_stored_snapshot_without_recomputing(self):
        self._seed_two_logs()
        logs = self.log_manager.list_logs(self.user_id)
        engine_inputs = self.log_manager.to_engine_inputs(logs)
        self.cache.get_or_compute_series(PROFILE, logs, engine_inputs)

        # Corrupt the stored snapshot so a genuine cache hit is distinguishable
        # from a fresh recompute: if get_or_compute_series recomputed, this
        # deliberately-wrong value would be overwritten and the assertion
        # below would fail.
        first_log = sorted(logs, key=lambda log: log.date)[0]
        stale = self.snapshot_dao.get(first_log.log_id, CompositionEngine.ENGINE_VERSION)
        object.__setattr__(stale, "bmi", -1.0)
        self.snapshot_dao.upsert(first_log.log_id, CompositionEngine.ENGINE_VERSION, stale)

        results = self.cache.get_or_compute_series(PROFILE, logs, engine_inputs)
        self.assertEqual(results[0].bmi, -1.0)

    def test_invalidate_clears_snapshots_for_the_user(self):
        self._seed_two_logs()
        logs = self.log_manager.list_logs(self.user_id)
        engine_inputs = self.log_manager.to_engine_inputs(logs)
        self.cache.get_or_compute_series(PROFILE, logs, engine_inputs)

        self.cache.invalidate_for_user(self.user_id)

        for log in logs:
            self.assertIsNone(
                self.snapshot_dao.get(log.log_id, CompositionEngine.ENGINE_VERSION)
            )

    def test_update_log_invalidates_the_cache(self):
        self._seed_two_logs()
        logs = self.log_manager.list_logs(self.user_id)
        engine_inputs = self.log_manager.to_engine_inputs(logs)
        self.cache.get_or_compute_series(PROFILE, logs, engine_inputs)

        first_log = sorted(logs, key=lambda log: log.date)[0]
        self.log_manager.update_log(first_log.log_id, weight_kg=96.0)

        self.assertIsNone(
            self.snapshot_dao.get(first_log.log_id, CompositionEngine.ENGINE_VERSION)
        )


if __name__ == "__main__":
    unittest.main()
