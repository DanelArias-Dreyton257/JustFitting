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
            username="demo_cut",
            email="demo_cut@example.com",
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

    def test_create_log_defaults_to_weekly_granularity(self):
        log = self.manager.create_log(
            user_id=self.user_id,
            log_date=date(2026, 1, 1),
            weight_kg=90.0,
            waist_cm=80.0,
            neck_cm=35.0,
            intake_kcal=2000,
            steps=5000,
        )
        self.assertEqual(log.granularity, "weekly")

    def test_create_log_accepts_daily_granularity(self):
        log = self.manager.create_log(
            user_id=self.user_id,
            log_date=date(2026, 1, 1),
            weight_kg=90.0,
            waist_cm=80.0,
            neck_cm=35.0,
            intake_kcal=2000,
            steps=5000,
            granularity="daily",
        )
        self.assertEqual(log.granularity, "daily")

    def test_create_log_rejects_invalid_granularity(self):
        with self.assertRaises(ValueError):
            self.manager.create_log(
                user_id=self.user_id,
                log_date=date(2026, 1, 1),
                weight_kg=90.0,
                waist_cm=80.0,
                neck_cm=35.0,
                intake_kcal=2000,
                steps=5000,
                granularity="monthly",
            )

    def test_update_log_round_trips_granularity_and_rejects_invalid(self):
        log = self.manager.create_log(
            user_id=self.user_id,
            log_date=date(2026, 1, 1),
            weight_kg=90.0,
            waist_cm=80.0,
            neck_cm=35.0,
            intake_kcal=2000,
            steps=5000,
        )
        updated = self.manager.update_log(log.log_id, granularity="daily")
        self.assertEqual(updated.granularity, "daily")

        with self.assertRaises(ValueError):
            self.manager.update_log(log.log_id, granularity="monthly")

    def test_create_log_allows_a_partial_row_missing_weight(self):
        """Phase 7.4 (partial logs, see README): weight_kg/waist_cm/
        neck_cm/intake_kcal/steps are individually optional now."""
        log = self.manager.create_log(
            user_id=self.user_id,
            log_date=date(2026, 1, 1),
            steps=7000,
            intake_kcal=2200,
        )
        self.assertIsNone(log.weight_kg)
        self.assertIsNone(log.waist_cm)
        self.assertIsNone(log.neck_cm)
        self.assertEqual(log.steps, 7000)
        self.assertEqual(log.intake_kcal, 2200)

    def test_create_log_still_rejects_a_negative_value_when_present(self):
        with self.assertRaises(ValueError):
            self.manager.create_log(
                user_id=self.user_id,
                log_date=date(2026, 1, 1),
                steps=-100,
            )

    def test_upsert_fields_creates_a_new_partial_row(self):
        log = self.manager.upsert_fields(
            self.user_id, date(2026, 1, 1), {"steps": 7000}, default_granularity="daily"
        )
        self.assertEqual(log.steps, 7000)
        self.assertIsNone(log.weight_kg)
        self.assertEqual(log.granularity, "daily")

    def test_upsert_fields_merges_into_an_existing_row_without_touching_other_fields(self):
        self.manager.upsert_fields(
            self.user_id, date(2026, 1, 1), {"steps": 7000}, default_granularity="daily"
        )
        merged = self.manager.upsert_fields(
            self.user_id,
            date(2026, 1, 1),
            {"intake_kcal": 2200, "carbs_g": 250, "fat_g": 70, "protein_g": 150},
        )
        self.assertEqual(merged.steps, 7000)  # untouched by the second call
        self.assertEqual(merged.intake_kcal, 2200)
        self.assertIsNone(merged.weight_kg)

    def test_upsert_fields_is_order_independent(self):
        """Steps-then-nutrition-then-body, or body-then-steps-then-
        nutrition -- either order converges on the same complete row
        (Phase 7.4's "whichever source arrives first" requirement)."""
        self.manager.upsert_fields(
            self.user_id, date(2026, 1, 1), {"steps": 7000}, default_granularity="daily"
        )
        self.manager.upsert_fields(
            self.user_id, date(2026, 1, 1), {"intake_kcal": 2200}
        )
        a = self.manager.upsert_fields(
            self.user_id,
            date(2026, 1, 1),
            {"weight_kg": 90.0, "waist_cm": 80.0, "neck_cm": 35.0},
        )

        self.manager.upsert_fields(
            self.user_id,
            date(2026, 1, 8),
            {"weight_kg": 90.0, "waist_cm": 80.0, "neck_cm": 35.0},
            default_granularity="daily",
        )
        self.manager.upsert_fields(
            self.user_id, date(2026, 1, 8), {"intake_kcal": 2200}
        )
        b = self.manager.upsert_fields(
            self.user_id, date(2026, 1, 8), {"steps": 7000}
        )

        self.assertEqual(
            (a.weight_kg, a.waist_cm, a.neck_cm, a.intake_kcal, a.steps),
            (b.weight_kg, b.waist_cm, b.neck_cm, b.intake_kcal, b.steps),
        )

    def test_upsert_fields_only_sets_granularity_on_first_creation(self):
        self.manager.upsert_fields(
            self.user_id, date(2026, 1, 1), {"weight_kg": 90.0}, default_granularity="weekly"
        )
        merged = self.manager.upsert_fields(
            self.user_id, date(2026, 1, 1), {"steps": 7000}, default_granularity="daily"
        )
        self.assertEqual(merged.granularity, "weekly")

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
