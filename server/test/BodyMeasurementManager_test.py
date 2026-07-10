"""Phase 9.1 (body composition logging separation, see README): sporadic
waist/neck (plus, since Phase 9.3, nine more record-only perimeters)
CRUD and the "static until next update" resolution rule.
"""

import unittest
from datetime import date

from server.src.data.db.AuditLogDAO import AuditLogDAO
from server.src.data.db.BodyMeasurementDAO import BodyMeasurementDAO
from server.src.data.db.DB import DB
from server.src.data.db.UserDAO import UserDAO
from server.src.services.BodyMeasurementManager import (
    BodyMeasurementManager,
    BodyMeasurementManagerError,
)


class BodyMeasurementManagerTest(unittest.TestCase):
    def setUp(self):
        self.db = DB(":memory:")
        self.manager = BodyMeasurementManager(BodyMeasurementDAO(self.db))
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

    def test_create_list_update_delete(self):
        measurement = self.manager.create(self.user_id, date(2026, 1, 1), waist_cm=91.0, neck_cm=38.5)
        self.assertEqual(len(self.manager.list_for_user(self.user_id)), 1)

        updated = self.manager.update(measurement.measurement_id, waist_cm=90.0)
        self.assertAlmostEqual(updated.waist_cm, 90.0)
        self.assertAlmostEqual(updated.neck_cm, 38.5)  # untouched

        self.manager.delete(measurement.measurement_id)
        self.assertEqual(self.manager.list_for_user(self.user_id), [])

    def test_create_rejects_waist_not_greater_than_neck(self):
        with self.assertRaises(BodyMeasurementManagerError):
            self.manager.create(self.user_id, date(2026, 1, 1), waist_cm=35.0, neck_cm=35.0)

    def test_create_rejects_a_non_positive_value(self):
        with self.assertRaises(BodyMeasurementManagerError):
            self.manager.create(self.user_id, date(2026, 1, 1), waist_cm=-1.0, neck_cm=35.0)

    def test_update_rejects_an_incoherent_merge(self):
        measurement = self.manager.create(self.user_id, date(2026, 1, 1), waist_cm=91.0, neck_cm=38.5)
        with self.assertRaises(BodyMeasurementManagerError):
            self.manager.update(measurement.measurement_id, neck_cm=95.0)  # now neck > waist

    def test_get_effective_returns_the_most_recent_measurement_on_or_before_the_date(self):
        self.manager.create(self.user_id, date(2026, 1, 1), waist_cm=91.0, neck_cm=38.5)
        self.manager.create(self.user_id, date(2026, 3, 1), waist_cm=85.0, neck_cm=37.0)

        self.assertIsNone(self.manager.get_effective(self.user_id, date(2025, 12, 31)))
        mid = self.manager.get_effective(self.user_id, date(2026, 2, 1))
        self.assertAlmostEqual(mid.waist_cm, 91.0)
        after = self.manager.get_effective(self.user_id, date(2026, 6, 1))
        self.assertAlmostEqual(after.waist_cm, 85.0)

    def test_upsert_for_date_creates_then_merges_without_a_duplicate_date_error(self):
        first = self.manager.upsert_for_date(
            self.user_id, date(2026, 1, 1), {"waist_cm": 91.0, "neck_cm": 38.5}
        )
        second = self.manager.upsert_for_date(
            self.user_id, date(2026, 1, 1), {"waist_cm": 90.0}
        )
        self.assertEqual(first.measurement_id, second.measurement_id)
        self.assertAlmostEqual(second.waist_cm, 90.0)
        self.assertAlmostEqual(second.neck_cm, 38.5)
        self.assertEqual(len(self.manager.list_for_user(self.user_id)), 1)

    def test_create_records_audit_entries_for_changed_fields(self):
        audit_log_dao = AuditLogDAO(self.db)
        manager = BodyMeasurementManager(BodyMeasurementDAO(self.db), audit_log_dao=audit_log_dao)
        measurement = manager.create(self.user_id, date(2026, 1, 1), waist_cm=91.0, neck_cm=38.5)

        manager.update(measurement.measurement_id, waist_cm=90.0)

        entries = audit_log_dao.list_for_user(self.user_id)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].entity_type, "body_measurement")
        self.assertEqual(entries[0].field, "waist_cm")
        self.assertEqual(entries[0].previous_value, "91.0")
        self.assertEqual(entries[0].new_value, "90.0")

    def test_mutations_invalidate_the_metrics_cache(self):
        calls = []

        class FakeCache:
            def invalidate_for_user(self, user_id):
                calls.append(user_id)

        manager = BodyMeasurementManager(BodyMeasurementDAO(self.db), metrics_cache=FakeCache())
        measurement = manager.create(self.user_id, date(2026, 1, 1), waist_cm=91.0, neck_cm=38.5)
        manager.update(measurement.measurement_id, waist_cm=90.0)
        manager.delete(measurement.measurement_id)

        self.assertEqual(calls, [self.user_id, self.user_id, self.user_id])

    def test_extended_phase_9_3_fields_round_trip(self):
        measurement = self.manager.create(
            self.user_id,
            date(2026, 1, 1),
            waist_cm=91.0,
            neck_cm=38.5,
            shoulder_cm=120.0,
            chest_cm=105.0,
            hips_cm=100.0,
            biceps_r_cm=35.0,
            biceps_l_cm=34.5,
            thigh_r_cm=60.0,
            thigh_l_cm=59.5,
            calf_r_cm=38.0,
            calf_l_cm=37.5,
        )
        self.assertEqual(measurement.shoulder_cm, 120.0)
        self.assertEqual(measurement.chest_cm, 105.0)
        self.assertEqual(measurement.hips_cm, 100.0)
        self.assertEqual(measurement.calf_l_cm, 37.5)


if __name__ == "__main__":
    unittest.main()
