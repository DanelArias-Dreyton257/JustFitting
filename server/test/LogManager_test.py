import unittest
from datetime import date

from server.src.data.db.AuditLogDAO import AuditLogDAO
from server.src.data.db.BodyLogDAO import BodyLogDAO
from server.src.data.db.DB import DB
from server.src.data.db.UserDAO import UserDAO
from server.src.services.composition.CompositionEngine import compute_series
from server.src.services.LogManager import LogManager, demo_profile_params


class LogManagerTest(unittest.TestCase):
    def setUp(self):
        self.db = DB(":memory:")
        self.user_dao = UserDAO(self.db)
        self.manager = LogManager(BodyLogDAO(self.db))
        self.user_id = self.user_dao.create(
            username="danel",
            email="danel@example.com",
            password_hash="hash",
            height_cm=176,
            sex=1,
            birthdate=date(2001, 8, 22),
        ).user_id

    def tearDown(self):
        self.db.close()

    def test_create_log_rejects_invalid_measurements(self):
        with self.assertRaises(ValueError):
            self.manager.create_log(
                user_id=self.user_id,
                log_date=date(2026, 1, 1),
                weight_kg=90.0,
                waist_cm=35.0,
                neck_cm=35.0,
                intake_kcal=2000,
                steps=5000,
            )
        with self.assertRaises(ValueError):
            self.manager.create_log(
                user_id=self.user_id,
                log_date=date(2026, 1, 1),
                weight_kg=-1,
                waist_cm=80.0,
                neck_cm=35.0,
                intake_kcal=2000,
                steps=5000,
            )

    def test_create_list_update_delete_log(self):
        log = self.manager.create_log(
            user_id=self.user_id,
            log_date=date(2026, 6, 26),
            weight_kg=90.7,
            waist_cm=80.0,
            neck_cm=35.0,
            intake_kcal=2014.30,
            steps=5000,
        )
        self.assertEqual(len(self.manager.list_logs(self.user_id)), 1)

        updated = self.manager.update_log(log.log_id, weight_kg=90.2)
        self.assertAlmostEqual(updated.weight_kg, 90.2)

        with self.assertRaises(ValueError):
            self.manager.update_log(log.log_id, waist_cm=30.0)

        self.manager.delete_log(log.log_id)
        self.assertEqual(self.manager.list_logs(self.user_id), [])

    def test_to_engine_inputs_feeds_composition_engine(self):
        self.manager.create_log(
            user_id=self.user_id,
            log_date=date(2025, 12, 28),
            weight_kg=97.0,
            waist_cm=91.0,
            neck_cm=38.5,
            intake_kcal=2400.0,
            steps=6000,
        )
        self.manager.create_log(
            user_id=self.user_id,
            log_date=date(2026, 1, 4),
            weight_kg=96.4,
            waist_cm=90.5,
            neck_cm=38.5,
            intake_kcal=2350.0,
            steps=6200,
        )
        logs = self.manager.list_logs(self.user_id)
        engine_inputs = self.manager.to_engine_inputs(logs)
        results = compute_series(demo_profile_params(), engine_inputs)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].weight_delta_kg, 0.0)

    def test_compute_adherence_uses_real_intake_rows_only(self):
        self.manager.create_log(
            user_id=self.user_id,
            log_date=date(2025, 12, 28),
            weight_kg=97.0,
            waist_cm=91.0,
            neck_cm=38.5,
            intake_kcal=2400.0,
            steps=6000,
            intake_is_real=True,
        )
        self.manager.create_log(
            user_id=self.user_id,
            log_date=date(2026, 1, 4),
            weight_kg=96.4,
            waist_cm=90.5,
            neck_cm=38.5,
            intake_kcal=2350.0,
            steps=6200,
            intake_is_real=False,
            source="projected",
        )
        logs = self.manager.list_logs(self.user_id)
        engine_inputs = self.manager.to_engine_inputs(logs)
        results = compute_series(demo_profile_params(), engine_inputs)

        adherence = self.manager.compute_adherence(logs, results)
        self.assertAlmostEqual(adherence, results[0].intake_diff)

    def test_seed_reference_series_is_idempotent(self):
        created = self.manager.seed_reference_series(self.user_id)
        self.assertGreater(len(created), 0)
        self.assertEqual(created[0].weight_kg, 97.0)
        self.assertEqual(created[-1].weight_kg, 90.7)

        second_call = self.manager.seed_reference_series(self.user_id)
        self.assertEqual(second_call, [])

    def test_update_log_records_audit_entries_for_changed_fields(self):
        audit_log_dao = AuditLogDAO(self.db)
        manager = LogManager(BodyLogDAO(self.db), audit_log_dao=audit_log_dao)
        log = manager.create_log(
            user_id=self.user_id,
            log_date=date(2026, 6, 26),
            weight_kg=90.7,
            waist_cm=80.0,
            neck_cm=35.0,
            intake_kcal=2014.30,
            steps=5000,
        )

        manager.update_log(log.log_id, weight_kg=90.2, steps=5000)

        entries = audit_log_dao.list_for_user(self.user_id)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].entity_type, "body_log")
        self.assertEqual(entries[0].field, "weight_kg")
        self.assertEqual(entries[0].previous_value, "90.7")
        self.assertEqual(entries[0].new_value, "90.2")


if __name__ == "__main__":
    unittest.main()
