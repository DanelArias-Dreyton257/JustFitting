import unittest
from datetime import date

from server.src.api.app import create_app


class ApiTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app({"DB_PATH": ":memory:", "TESTING": True})
        self.client = self.app.test_client()

    def tearDown(self):
        self.app.extensions["db"].close()

    def _register(
        self, username="demo_cut", email="demo_cut@example.com", password="hunter22"
    ):
        return self.client.post(
            "/api/users",
            json={
                "username": username,
                "email": email,
                "password": password,
                "height_cm": 176,
                "sex": 1,
                "birthdate": "2001-08-22",
                "target_bf": 0.15,
                "weekly_rate": -0.005,
            },
        )

    def _auth_header(self, token):
        return {"Authorization": f"Bearer {token}"}

    def test_health(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"status": "ok"})

    def test_register_login_me_logout(self):
        register_response = self._register()
        self.assertEqual(register_response.status_code, 201)
        token = register_response.get_json()["token"]

        login_response = self.client.post(
            "/api/auth/login", json={"username": "demo_cut", "password": "hunter22"}
        )
        self.assertEqual(login_response.status_code, 200)
        login_token = login_response.get_json()["token"]

        me_response = self.client.get(
            "/api/users/me", headers=self._auth_header(login_token)
        )
        self.assertEqual(me_response.status_code, 200)
        self.assertEqual(me_response.get_json()["username"], "demo_cut")

        logout_response = self.client.post(
            "/api/auth/logout", headers=self._auth_header(login_token)
        )
        self.assertEqual(logout_response.status_code, 204)

        me_after_logout = self.client.get(
            "/api/users/me", headers=self._auth_header(login_token)
        )
        self.assertEqual(me_after_logout.status_code, 401)

        # First token issued at registration is a separate session and still valid.
        still_valid = self.client.get("/api/users/me", headers=self._auth_header(token))
        self.assertEqual(still_valid.status_code, 200)

    def test_register_without_goal_fields_resolves_sane_per_sex_defaults(self):
        # Phase 5.2: registration no longer requires target_bf/weekly_rate.
        male_response = self.client.post(
            "/api/users",
            json={
                "username": "male_default",
                "email": "male_default@example.com",
                "password": "hunter22",
                "height_cm": 176,
                "sex": 1,
                "birthdate": "2001-08-22",
            },
        )
        self.assertEqual(male_response.status_code, 201)
        male_profile = male_response.get_json()["profile"]
        self.assertAlmostEqual(male_profile["target_bf"], 0.15)
        self.assertAlmostEqual(male_profile["weekly_rate"], 0.0)

        female_response = self.client.post(
            "/api/users",
            json={
                "username": "female_default",
                "email": "female_default@example.com",
                "password": "hunter22",
                "height_cm": 165,
                "sex": 0,
                "birthdate": "2001-08-22",
            },
        )
        self.assertEqual(female_response.status_code, 201)
        female_profile = female_response.get_json()["profile"]
        self.assertAlmostEqual(female_profile["target_bf"], 0.22)
        self.assertAlmostEqual(female_profile["weekly_rate"], 0.0)

    def test_register_rejects_duplicate_username(self):
        self._register()
        duplicate = self._register(email="other@example.com")
        self.assertEqual(duplicate.status_code, 400)

    def test_protected_routes_require_token(self):
        response = self.client.get("/api/users/me")
        self.assertEqual(response.status_code, 401)

    def test_update_profile_and_change_password(self):
        token = self._register().get_json()["token"]
        headers = self._auth_header(token)

        update_response = self.client.put(
            "/api/users/me", json={"height_cm": 180}, headers=headers
        )
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(update_response.get_json()["height_cm"], 180)

        password_response = self.client.post(
            "/api/users/me/password",
            json={"old_password": "hunter22", "new_password": "new-password-1"},
            headers=headers,
        )
        self.assertEqual(password_response.status_code, 204)

        relogin = self.client.post(
            "/api/auth/login", json={"username": "demo_cut", "password": "new-password-1"}
        )
        self.assertEqual(relogin.status_code, 200)

    def test_log_crud_lifecycle(self):
        token = self._register().get_json()["token"]
        headers = self._auth_header(token)

        create_response = self.client.post(
            "/api/logs",
            json={
                "date": "2026-06-26",
                "weight_kg": 90.7,
                "waist_cm": 80.0,
                "neck_cm": 35.0,
                "intake_kcal": 2014.30,
                "steps": 5000,
            },
            headers=headers,
        )
        self.assertEqual(create_response.status_code, 201)
        log_id = create_response.get_json()["log_id"]

        list_response = self.client.get("/api/logs", headers=headers)
        self.assertEqual(len(list_response.get_json()), 1)

        update_response = self.client.put(
            f"/api/logs/{log_id}", json={"weight_kg": 90.2}, headers=headers
        )
        self.assertEqual(update_response.status_code, 200)
        self.assertAlmostEqual(update_response.get_json()["weight_kg"], 90.2)

        invalid_update = self.client.put(
            f"/api/logs/{log_id}", json={"waist_cm": 10.0}, headers=headers
        )
        self.assertEqual(invalid_update.status_code, 400)

        delete_response = self.client.delete(f"/api/logs/{log_id}", headers=headers)
        self.assertEqual(delete_response.status_code, 204)

        missing_update = self.client.put(
            f"/api/logs/{log_id}", json={"weight_kg": 91.0}, headers=headers
        )
        self.assertEqual(missing_update.status_code, 404)

    def test_upsert_by_date_creates_a_partial_row_then_merges_more_fields_in(self):
        """Phase 7.4 (partial logs & independent-source merging, see
        README): PUT /api/logs/by-date/<date> is the order-independent
        primitive a future Health Connect sync uses -- steps first, then
        nutrition, then body measurements, each only touching its own
        fields."""
        token = self._register().get_json()["token"]
        headers = self._auth_header(token)

        steps_response = self.client.put(
            "/api/logs/by-date/2026-02-01",
            json={"steps": 7000, "granularity": "daily"},
            headers=headers,
        )
        self.assertEqual(steps_response.status_code, 200)
        body = steps_response.get_json()
        self.assertEqual(body["steps"], 7000)
        self.assertIsNone(body["weight_kg"])
        self.assertEqual(body["granularity"], "daily")
        log_id = body["log_id"]

        nutrition_response = self.client.put(
            "/api/logs/by-date/2026-02-01",
            json={"intake_kcal": 2200, "carbs_g": 250, "fat_g": 70, "protein_g": 150},
            headers=headers,
        )
        self.assertEqual(nutrition_response.status_code, 200)
        body = nutrition_response.get_json()
        self.assertEqual(body["log_id"], log_id)  # same row, merged in
        self.assertEqual(body["steps"], 7000)  # untouched by this call
        self.assertEqual(body["intake_kcal"], 2200)

        body_response = self.client.put(
            "/api/logs/by-date/2026-02-01",
            json={"weight_kg": 90.0, "waist_cm": 80.0, "neck_cm": 35.0},
            headers=headers,
        )
        self.assertEqual(body_response.status_code, 200)
        body = body_response.get_json()
        self.assertEqual(body["log_id"], log_id)
        self.assertEqual(body["weight_kg"], 90.0)
        self.assertEqual(body["steps"], 7000)
        self.assertEqual(body["intake_kcal"], 2200)
        # Only ever set once, on first creation (by the steps write above).
        self.assertEqual(body["granularity"], "daily")

        list_response = self.client.get("/api/logs", headers=headers)
        self.assertEqual(len(list_response.get_json()), 1)

    def test_upsert_by_date_rejects_an_invalid_value(self):
        token = self._register().get_json()["token"]
        headers = self._auth_header(token)

        response = self.client.put(
            "/api/logs/by-date/2026-02-01",
            json={"weight_kg": -5.0},
            headers=headers,
        )
        self.assertEqual(response.status_code, 400)

    def test_upsert_by_date_rejects_a_malformed_date(self):
        token = self._register().get_json()["token"]
        headers = self._auth_header(token)

        response = self.client.put(
            "/api/logs/by-date/not-a-date",
            json={"steps": 7000},
            headers=headers,
        )
        self.assertEqual(response.status_code, 400)

    def test_log_create_and_update_persist_cardio_kcal(self):
        token = self._register().get_json()["token"]
        headers = self._auth_header(token)

        create_response = self.client.post(
            "/api/logs",
            json={
                "date": "2026-06-26",
                "weight_kg": 90.7,
                "waist_cm": 80.0,
                "neck_cm": 35.0,
                "intake_kcal": 2014.30,
                "steps": 5000,
                "cardio_kcal": 300.0,
            },
            headers=headers,
        )
        self.assertEqual(create_response.status_code, 201)
        body = create_response.get_json()
        self.assertAlmostEqual(body["cardio_kcal"], 300.0)
        log_id = body["log_id"]

        update_response = self.client.put(
            f"/api/logs/{log_id}", json={"cardio_kcal": 450.0}, headers=headers
        )
        self.assertAlmostEqual(update_response.get_json()["cardio_kcal"], 450.0)

    def test_log_create_defaults_cardio_kcal_to_zero(self):
        token = self._register().get_json()["token"]
        response = self.client.post(
            "/api/logs",
            json={
                "date": "2026-06-26",
                "weight_kg": 90.7,
                "waist_cm": 80.0,
                "neck_cm": 35.0,
                "intake_kcal": 2014.30,
                "steps": 5000,
            },
            headers=self._auth_header(token),
        )
        self.assertAlmostEqual(response.get_json()["cardio_kcal"], 0.0)

    def test_log_create_and_update_persist_granularity(self):
        token = self._register().get_json()["token"]
        headers = self._auth_header(token)

        create_response = self.client.post(
            "/api/logs",
            json={
                "date": "2026-06-26",
                "weight_kg": 90.7,
                "waist_cm": 80.0,
                "neck_cm": 35.0,
                "intake_kcal": 2014.30,
                "steps": 5000,
                "granularity": "daily",
            },
            headers=headers,
        )
        self.assertEqual(create_response.status_code, 201)
        body = create_response.get_json()
        self.assertEqual(body["granularity"], "daily")
        log_id = body["log_id"]

        update_response = self.client.put(
            f"/api/logs/{log_id}", json={"granularity": "weekly"}, headers=headers
        )
        self.assertEqual(update_response.get_json()["granularity"], "weekly")

    def test_log_create_defaults_granularity_to_weekly(self):
        token = self._register().get_json()["token"]
        response = self.client.post(
            "/api/logs",
            json={
                "date": "2026-06-26",
                "weight_kg": 90.7,
                "waist_cm": 80.0,
                "neck_cm": 35.0,
                "intake_kcal": 2014.30,
                "steps": 5000,
            },
            headers=self._auth_header(token),
        )
        self.assertEqual(response.get_json()["granularity"], "weekly")

    def test_log_create_and_update_persist_macros(self):
        token = self._register().get_json()["token"]
        headers = self._auth_header(token)

        create_response = self.client.post(
            "/api/logs",
            json={
                "date": "2026-06-26",
                "weight_kg": 90.7,
                "waist_cm": 80.0,
                "neck_cm": 35.0,
                "intake_kcal": 2014.30,
                "steps": 5000,
                "granularity": "daily",
                "carbs_g": 200.0,
                "fat_g": 70.0,
                "protein_g": 180.0,
            },
            headers=headers,
        )
        self.assertEqual(create_response.status_code, 201)
        body = create_response.get_json()
        self.assertAlmostEqual(body["carbs_g"], 200.0)
        self.assertAlmostEqual(body["fat_g"], 70.0)
        self.assertAlmostEqual(body["protein_g"], 180.0)
        log_id = body["log_id"]

        update_response = self.client.put(
            f"/api/logs/{log_id}", json={"carbs_g": 210.0}, headers=headers
        )
        self.assertAlmostEqual(update_response.get_json()["carbs_g"], 210.0)

    def test_log_create_defaults_macros_to_null(self):
        token = self._register().get_json()["token"]
        response = self.client.post(
            "/api/logs",
            json={
                "date": "2026-06-26",
                "weight_kg": 90.7,
                "waist_cm": 80.0,
                "neck_cm": 35.0,
                "intake_kcal": 2014.30,
                "steps": 5000,
            },
            headers=self._auth_header(token),
        )
        body = response.get_json()
        self.assertIsNone(body["carbs_g"])
        self.assertIsNone(body["fat_g"])
        self.assertIsNone(body["protein_g"])

    def test_log_create_rejects_partial_macros(self):
        token = self._register().get_json()["token"]
        response = self.client.post(
            "/api/logs",
            json={
                "date": "2026-06-26",
                "weight_kg": 90.7,
                "waist_cm": 80.0,
                "neck_cm": 35.0,
                "intake_kcal": 2014.30,
                "steps": 5000,
                "carbs_g": 200.0,
            },
            headers=self._auth_header(token),
        )
        self.assertEqual(response.status_code, 400)

    def test_log_create_rejects_invalid_granularity(self):
        token = self._register().get_json()["token"]
        response = self.client.post(
            "/api/logs",
            json={
                "date": "2026-06-26",
                "weight_kg": 90.7,
                "waist_cm": 80.0,
                "neck_cm": 35.0,
                "intake_kcal": 2014.30,
                "steps": 5000,
                "granularity": "monthly",
            },
            headers=self._auth_header(token),
        )
        self.assertEqual(response.status_code, 400)

    def test_daily_logs_within_one_iso_week_collapse_in_metrics_series(self):
        token = self._register().get_json()["token"]
        headers = self._auth_header(token)

        # A prior weekly baseline, then a full ISO week (2026-W02, Mon 1/5..Sun 1/11)
        # logged daily -- should collapse to exactly one extra metrics row.
        self.client.post(
            "/api/logs",
            json={
                "date": "2025-12-28",
                "weight_kg": 97.0,
                "waist_cm": 91.0,
                "neck_cm": 38.5,
                "intake_kcal": 2400.0,
                "steps": 6000,
            },
            headers=headers,
        )
        daily_weights = [96.0, 95.8, 95.9, 95.7, 95.6, 95.5, 95.4]
        for offset, weight in enumerate(daily_weights):
            day = 5 + offset
            self.client.post(
                "/api/logs",
                json={
                    "date": f"2026-01-{day:02d}",
                    "weight_kg": weight,
                    "waist_cm": 90.0,
                    "neck_cm": 38.5,
                    "intake_kcal": 2300.0,
                    "steps": 6100,
                    "granularity": "daily",
                },
                headers=headers,
            )

        raw_logs = self.client.get("/api/logs", headers=headers).get_json()
        self.assertEqual(len(raw_logs), 8)

        series_response = self.client.get("/api/metrics/series", headers=headers)
        series = series_response.get_json()
        self.assertEqual(len(series), 2)
        self.assertEqual(series[1]["date"], "2026-01-11")

    def test_log_create_rejects_invalid_navy_ratio(self):
        token = self._register().get_json()["token"]
        headers = self._auth_header(token)
        response = self.client.post(
            "/api/logs",
            json={
                "date": "2026-06-26",
                "weight_kg": 90.7,
                "waist_cm": 30.0,
                "neck_cm": 35.0,
                "intake_kcal": 2000,
                "steps": 5000,
            },
            headers=headers,
        )
        self.assertEqual(response.status_code, 400)

    def _seed_two_logs(self, headers):
        self.client.post(
            "/api/logs",
            json={
                "date": "2025-12-28",
                "weight_kg": 97.0,
                "waist_cm": 91.0,
                "neck_cm": 38.5,
                "intake_kcal": 2400.0,
                "steps": 6000,
            },
            headers=headers,
        )
        self.client.post(
            "/api/logs",
            json={
                "date": "2026-01-04",
                "weight_kg": 96.4,
                "waist_cm": 90.5,
                "neck_cm": 38.5,
                "intake_kcal": 2350.0,
                "steps": 6200,
            },
            headers=headers,
        )

    def test_metrics_latest_and_series(self):
        token = self._register().get_json()["token"]
        headers = self._auth_header(token)
        self._seed_two_logs(headers)

        latest_response = self.client.get("/api/metrics/latest", headers=headers)
        self.assertEqual(latest_response.status_code, 200)
        self.assertEqual(latest_response.get_json()["date"], "2026-01-04")

        series_response = self.client.get("/api/metrics/series", headers=headers)
        self.assertEqual(len(series_response.get_json()), 2)

    def test_metrics_latest_without_logs_returns_404(self):
        token = self._register().get_json()["token"]
        response = self.client.get(
            "/api/metrics/latest", headers=self._auth_header(token)
        )
        self.assertEqual(response.status_code, 404)

    def test_projection_endpoint(self):
        token = self._register().get_json()["token"]
        headers = self._auth_header(token)
        self._seed_two_logs(headers)

        response = self.client.get("/api/projection?weeks=3", headers=headers)
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(len(body), 3)
        self.assertTrue(all(row["source"] == "projected" for row in body))
        self.assertTrue(
            all(
                isinstance(row["estimated_weight"], (int, float))
                and isinstance(row["estimated_waist"], (int, float))
                and isinstance(row["estimated_neck"], (int, float))
                for row in body
            )
        )

    def test_export_and_import_roundtrip(self):
        token = self._register().get_json()["token"]
        headers = self._auth_header(token)
        self._seed_two_logs(headers)

        export_response = self.client.get("/api/users/me/export", headers=headers)
        self.assertEqual(export_response.status_code, 200)
        exported = export_response.get_json()
        self.assertEqual(len(exported["logs"]), 2)

        other_token = self._register(
            username="other", email="other@example.com"
        ).get_json()["token"]
        other_headers = self._auth_header(other_token)
        import_response = self.client.post(
            "/api/users/me/import",
            json={"logs": exported["logs"]},
            headers=other_headers,
        )
        self.assertEqual(import_response.status_code, 201)
        self.assertEqual(import_response.get_json()["imported"], 2)

    def test_import_preserves_granularity_and_macros(self):
        token = self._register().get_json()["token"]
        headers = self._auth_header(token)

        response = self.client.post(
            "/api/users/me/import",
            json={
                "logs": [
                    {
                        "date": "2026-02-01",
                        "weight_kg": 90.0,
                        "waist_cm": 88.0,
                        "neck_cm": 37.0,
                        "intake_kcal": 2200,
                        "steps": 7000,
                        "granularity": "daily",
                        "carbs_g": 200.0,
                        "fat_g": 60.0,
                        "protein_g": 150.0,
                    }
                ]
            },
            headers=headers,
        )
        self.assertEqual(response.status_code, 201)
        body = response.get_json()
        self.assertEqual(body["imported"], 1)
        self.assertEqual(body["skipped"], [])
        imported_log = body["logs"][0]
        self.assertEqual(imported_log["granularity"], "daily")
        self.assertEqual(imported_log["carbs_g"], 200.0)
        self.assertEqual(imported_log["fat_g"], 60.0)
        self.assertEqual(imported_log["protein_g"], 150.0)

    def test_import_skips_duplicate_date_with_reason_and_keeps_the_rest(self):
        token = self._register().get_json()["token"]
        headers = self._auth_header(token)
        self._seed_two_logs(headers)

        response = self.client.post(
            "/api/users/me/import",
            json={
                "logs": [
                    {  # collides with _seed_two_logs' first row
                        "date": "2025-12-28",
                        "weight_kg": 99.0,
                        "waist_cm": 92.0,
                        "neck_cm": 39.0,
                        "intake_kcal": 2500,
                        "steps": 5500,
                    },
                    {
                        "date": "2026-02-08",
                        "weight_kg": 95.0,
                        "waist_cm": 89.0,
                        "neck_cm": 38.0,
                        "intake_kcal": 2300,
                        "steps": 6800,
                    },
                ]
            },
            headers=headers,
        )
        self.assertEqual(response.status_code, 201)
        body = response.get_json()
        self.assertEqual(body["imported"], 1)
        self.assertEqual(len(body["skipped"]), 1)
        self.assertEqual(body["skipped"][0], {"row": 0, "reason": "duplicate date"})

        # The colliding date's original row is untouched, not overwritten.
        logs_response = self.client.get("/api/logs", headers=headers)
        original_row = next(
            row for row in logs_response.get_json() if row["date"] == "2025-12-28"
        )
        self.assertEqual(original_row["weight_kg"], 97.0)

    def test_import_forces_source_real_regardless_of_the_file(self):
        token = self._register().get_json()["token"]
        headers = self._auth_header(token)

        response = self.client.post(
            "/api/users/me/import",
            json={
                "logs": [
                    {
                        "date": "2026-02-01",
                        "weight_kg": 90.0,
                        "waist_cm": 88.0,
                        "neck_cm": 37.0,
                        "intake_kcal": 2200,
                        "steps": 7000,
                        "source": "projected",
                    }
                ]
            },
            headers=headers,
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()["logs"][0]["source"], "real")

    def test_import_reports_a_reason_for_an_invalid_row(self):
        token = self._register().get_json()["token"]
        headers = self._auth_header(token)

        response = self.client.post(
            "/api/users/me/import",
            json={
                "logs": [
                    {
                        "date": "2026-02-01",
                        "weight_kg": -5.0,  # invalid: must be positive
                        "waist_cm": 88.0,
                        "neck_cm": 37.0,
                        "intake_kcal": 2200,
                        "steps": 7000,
                    }
                ]
            },
            headers=headers,
        )
        self.assertEqual(response.status_code, 201)
        body = response.get_json()
        self.assertEqual(body["imported"], 0)
        self.assertEqual(len(body["skipped"]), 1)
        self.assertEqual(body["skipped"][0]["row"], 0)
        self.assertIn("weight_kg", body["skipped"][0]["reason"])

    def test_import_accepts_a_partial_row_missing_weight(self):
        """Phase 7.4 (partial logs, see README): weight_kg (and the other
        four core measurements) are no longer required on import -- a row
        can be steps/nutrition-only, matching what a Health Connect sync
        would send."""
        token = self._register().get_json()["token"]
        headers = self._auth_header(token)

        response = self.client.post(
            "/api/users/me/import",
            json={
                "logs": [
                    {
                        "date": "2026-02-01",
                        "steps": 7000,
                        "intake_kcal": 2200,
                    }
                ]
            },
            headers=headers,
        )
        self.assertEqual(response.status_code, 201)
        body = response.get_json()
        self.assertEqual(body["imported"], 1)
        self.assertEqual(body["skipped"], [])
        imported_log = body["logs"][0]
        self.assertIsNone(imported_log["weight_kg"])
        self.assertIsNone(imported_log["waist_cm"])
        self.assertIsNone(imported_log["neck_cm"])
        self.assertEqual(imported_log["steps"], 7000)
        self.assertEqual(imported_log["intake_kcal"], 2200)

    def test_delete_account(self):
        token = self._register().get_json()["token"]
        headers = self._auth_header(token)
        response = self.client.delete("/api/users/me", headers=headers)
        self.assertEqual(response.status_code, 204)

        me_response = self.client.get("/api/users/me", headers=headers)
        self.assertEqual(me_response.status_code, 401)

    def test_register_reflects_the_active_goal_plan(self):
        response = self._register()
        profile = response.get_json()["profile"]
        self.assertAlmostEqual(profile["target_bf"], 0.15)
        self.assertAlmostEqual(profile["weekly_rate"], -0.005)

    def test_update_profile_goal_fields_historizes_the_goal(self):
        token = self._register().get_json()["token"]
        headers = self._auth_header(token)

        update_response = self.client.put(
            "/api/users/me",
            json={"target_bf": 0.2, "weekly_rate": -0.01},
            headers=headers,
        )
        self.assertEqual(update_response.status_code, 200)
        profile = update_response.get_json()
        self.assertAlmostEqual(profile["target_bf"], 0.2)
        self.assertAlmostEqual(profile["weekly_rate"], -0.01)

        goals_response = self.client.get("/api/users/me/goals", headers=headers)
        self.assertEqual(goals_response.status_code, 200)
        goals = goals_response.get_json()
        self.assertEqual(len(goals), 2)
        self.assertTrue(goals[0]["active"])
        self.assertFalse(goals[1]["active"])
        self.assertEqual(goals[0]["direction"], "cut")

    def test_metrics_series_excludes_logs_from_before_a_goal_change(self):
        # Phase 5.3: once an account actually changes its goal, the derived
        # series only ever sees that goal's own period -- otherwise
        # changing goals silently recomputes old weeks as if the new goal
        # had applied the whole time.
        token = self._register().get_json()["token"]
        headers = self._auth_header(token)
        self._seed_two_logs(headers)

        before = self.client.get("/api/metrics/series", headers=headers).get_json()
        self.assertEqual(len(before), 2)

        self.client.put("/api/users/me", json={"target_bf": 0.2}, headers=headers)

        after = self.client.get("/api/metrics/series", headers=headers).get_json()
        self.assertEqual(after, [])

        # The raw log list (and by extension /export's "logs" key) is
        # unaffected -- full history stays reachable there, same
        # "not a data-loss concern" precedent Phase 4.4 established.
        raw_logs = self.client.get("/api/logs", headers=headers).get_json()
        self.assertEqual(len(raw_logs), 2)

    def test_metrics_series_includes_a_log_on_or_after_the_goal_change(self):
        token = self._register().get_json()["token"]
        headers = self._auth_header(token)
        self._seed_two_logs(headers)
        self.client.put("/api/users/me", json={"target_bf": 0.2}, headers=headers)

        today_iso = date.today().isoformat()
        self.client.post(
            "/api/logs",
            json={
                "date": today_iso,
                "weight_kg": 95.0,
                "waist_cm": 90.0,
                "neck_cm": 38.0,
                "intake_kcal": 2200.0,
                "steps": 6000,
            },
            headers=headers,
        )

        after = self.client.get("/api/metrics/series", headers=headers).get_json()
        self.assertEqual(len(after), 1)
        self.assertEqual(after[0]["date"], today_iso)

    def test_metrics_series_unaffected_for_an_account_that_never_changes_its_goal(self):
        # The no-op guarantee: a never-changed goal (even one whose
        # start_date is "today", from registration) must never exclude a
        # log dated before it.
        token = self._register().get_json()["token"]
        headers = self._auth_header(token)
        self._seed_two_logs(headers)

        series = self.client.get("/api/metrics/series", headers=headers).get_json()
        self.assertEqual(len(series), 2)

    def test_projection_regression_excludes_logs_from_before_a_goal_change(self):
        token = self._register().get_json()["token"]
        headers = self._auth_header(token)
        self._seed_two_logs(headers)
        self.client.put("/api/users/me", json={"target_bf": 0.2}, headers=headers)

        # Both real logs predate the goal change, so the forecast's
        # regression source is now empty -- same 400 a fresh account with
        # fewer than two real logs would get.
        response = self.client.get("/api/projection?weeks=2", headers=headers)
        self.assertEqual(response.status_code, 400)

    def test_goal_direction_is_bulk_for_a_positive_weekly_rate(self):
        token = self._register().get_json()["token"]
        headers = self._auth_header(token)
        update_response = self.client.put(
            "/api/users/me",
            json={"weekly_rate": 0.003},
            headers=headers,
        )
        self.assertEqual(update_response.get_json()["direction"], "bulk")
        goals = self.client.get("/api/users/me/goals", headers=headers).get_json()
        self.assertEqual(goals[0]["direction"], "bulk")

    def test_log_edit_is_recorded_in_the_audit_log(self):
        token = self._register().get_json()["token"]
        headers = self._auth_header(token)
        create_response = self.client.post(
            "/api/logs",
            json={
                "date": "2026-06-26",
                "weight_kg": 90.7,
                "waist_cm": 80.0,
                "neck_cm": 35.0,
                "intake_kcal": 2014.30,
                "steps": 5000,
            },
            headers=headers,
        )
        log_id = create_response.get_json()["log_id"]

        self.client.put(
            f"/api/logs/{log_id}", json={"weight_kg": 90.2}, headers=headers
        )

        audit_response = self.client.get("/api/users/me/audit-log", headers=headers)
        self.assertEqual(audit_response.status_code, 200)
        entries = audit_response.get_json()
        log_entries = [e for e in entries if e["entity_type"] == "body_log"]
        self.assertEqual(len(log_entries), 1)
        self.assertEqual(log_entries[0]["field"], "weight_kg")

    def test_save_and_retrieve_a_projection_run(self):
        token = self._register().get_json()["token"]
        headers = self._auth_header(token)
        self._seed_two_logs(headers)

        save_response = self.client.post(
            "/api/projection?weeks=3", headers=headers
        )
        self.assertEqual(save_response.status_code, 201)
        body = save_response.get_json()
        run_id = body["run_id"]
        self.assertEqual(len(body["rows"]), 3)

        runs_response = self.client.get("/api/projections", headers=headers)
        self.assertEqual(runs_response.status_code, 200)
        runs = runs_response.get_json()
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]["run_id"], run_id)

        run_response = self.client.get(f"/api/projections/{run_id}", headers=headers)
        self.assertEqual(run_response.status_code, 200)
        self.assertEqual(len(run_response.get_json()), 3)

    def test_metrics_series_is_cached_across_reads(self):
        token = self._register().get_json()["token"]
        headers = self._auth_header(token)
        self._seed_two_logs(headers)

        first = self.client.get("/api/metrics/series", headers=headers).get_json()
        second = self.client.get("/api/metrics/series", headers=headers).get_json()
        self.assertEqual(first, second)
        self.assertIsNotNone(first[0]["log_id"])
        self.assertIsNotNone(first[0]["engine_version"])

    def test_plan_preview_matches_current_plan_when_no_overrides_given(self):
        token = self._register().get_json()["token"]
        headers = self._auth_header(token)
        self._seed_two_logs(headers)

        latest = self.client.get("/api/metrics/latest", headers=headers).get_json()
        preview = self.client.get("/api/plan/preview", headers=headers)
        self.assertEqual(preview.status_code, 200)
        body = preview.get_json()
        self.assertAlmostEqual(body["target_calories"], latest["target_calories"], places=2)
        self.assertAlmostEqual(body["weeks_to_goal"], latest["weeks_to_goal"], places=2)

    def test_plan_preview_reflects_a_candidate_weekly_rate(self):
        token = self._register().get_json()["token"]
        headers = self._auth_header(token)
        self._seed_two_logs(headers)

        slower = self.client.get(
            "/api/plan/preview?weekly_rate=-0.002", headers=headers
        ).get_json()
        faster = self.client.get(
            "/api/plan/preview?weekly_rate=-0.01", headers=headers
        ).get_json()
        # A faster weekly loss rate implies a lower target-calorie intake
        # and fewer weeks to reach the goal.
        self.assertLess(faster["target_calories"], slower["target_calories"])
        self.assertLess(faster["weeks_to_goal"], slower["weeks_to_goal"])

    def test_plan_preview_does_not_persist_a_new_goal(self):
        token = self._register().get_json()["token"]
        headers = self._auth_header(token)
        self._seed_two_logs(headers)

        self.client.get("/api/plan/preview?target_bf=0.25", headers=headers)

        goals_response = self.client.get("/api/users/me/goals", headers=headers)
        self.assertEqual(len(goals_response.get_json()), 1)

    def test_plan_preview_without_logs_returns_404(self):
        token = self._register().get_json()["token"]
        response = self.client.get(
            "/api/plan/preview", headers=self._auth_header(token)
        )
        self.assertEqual(response.status_code, 404)

    def test_export_includes_goal_history_and_audit_log(self):
        token = self._register().get_json()["token"]
        headers = self._auth_header(token)
        self._seed_two_logs(headers)
        self.client.put(
            "/api/users/me", json={"target_bf": 0.2}, headers=headers
        )

        export_response = self.client.get("/api/users/me/export", headers=headers)
        exported = export_response.get_json()
        self.assertEqual(len(exported["goal_history"]), 2)
        self.assertGreaterEqual(len(exported["audit_log"]), 1)

    def test_export_includes_wave2_metrics(self):
        token = self._register().get_json()["token"]
        headers = self._auth_header(token)
        self._seed_two_logs(headers)

        export_response = self.client.get("/api/users/me/export", headers=headers)
        exported = export_response.get_json()
        for key in ("gain_quality", "energy_balance", "increment_analytics", "tef", "macro_targets"):
            self.assertIn(key, exported)
        self.assertEqual(len(exported["gain_quality"]), 2)
        self.assertEqual(len(exported["tef"]), 2)

    def test_alerts_empty_without_logs(self):
        token = self._register().get_json()["token"]
        response = self.client.get("/api/alerts", headers=self._auth_header(token))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), [])

    def test_alerts_flags_an_unconfigured_default_goal_with_zero_logs(self):
        # Phase 5.2 follow-up: registering without target_bf/weekly_rate
        # (the real register form's path since Phase 5.2) resolves to a 0%
        # weekly rate, which should surface a dismissible reminder to visit
        # the Plan tab -- even before any log exists.
        response = self.client.post(
            "/api/users",
            json={
                "username": "noplan",
                "email": "noplan@example.com",
                "password": "hunter22",
                "height_cm": 176,
                "sex": 1,
                "birthdate": "2001-08-22",
            },
        )
        token = response.get_json()["token"]
        alerts = self.client.get(
            "/api/alerts", headers=self._auth_header(token)
        ).get_json()
        flagged = [a for a in alerts if a["type"] == "unconfigured_goal"]
        self.assertEqual(len(flagged), 1)
        self.assertEqual(flagged[0]["severity"], "info")

    def test_alerts_flags_an_implausible_weekly_change(self):
        token = self._register().get_json()["token"]
        headers = self._auth_header(token)
        self.client.post(
            "/api/logs",
            json={
                "date": "2025-12-28",
                "weight_kg": 97.0,
                "waist_cm": 91.0,
                "neck_cm": 38.5,
                "intake_kcal": 2400.0,
                "steps": 6000,
            },
            headers=headers,
        )
        self.client.post(
            "/api/logs",
            json={
                "date": "2026-01-04",
                "weight_kg": 89.0,  # >8% down in one week
                "waist_cm": 89.0,
                "neck_cm": 38.0,
                "intake_kcal": 2000.0,
                "steps": 6000,
            },
            headers=headers,
        )

        response = self.client.get("/api/alerts", headers=headers)
        self.assertEqual(response.status_code, 200)
        alerts = response.get_json()
        implausible = [a for a in alerts if a["type"] == "implausible_change"]
        self.assertEqual(len(implausible), 1)
        self.assertEqual(implausible[0]["date"], "2026-01-04")
        self.assertEqual(implausible[0]["severity"], "warning")

    def test_alerts_flags_a_significant_goal_deviation(self):
        token = self._register().get_json()["token"]
        headers = self._auth_header(token)
        self._seed_two_logs(headers)
        # weekly_rate=-0.005 on 97.0kg objects ~90.545g change; logging a
        # weight far above that objective should trip the deviation alert.
        self.client.post(
            "/api/logs",
            json={
                "date": "2026-01-11",
                "weight_kg": 98.0,
                "waist_cm": 90.0,
                "neck_cm": 38.5,
                "intake_kcal": 2300.0,
                "steps": 6000,
            },
            headers=headers,
        )

        response = self.client.get("/api/alerts", headers=headers)
        self.assertEqual(response.status_code, 200)
        alerts = response.get_json()
        deviation = [a for a in alerts if a["type"] == "deviation"]
        self.assertTrue(any(a["date"] == "2026-01-11" for a in deviation))

    def test_adherence_without_logs_returns_404(self):
        token = self._register().get_json()["token"]
        response = self.client.get(
            "/api/metrics/adherence", headers=self._auth_header(token)
        )
        self.assertEqual(response.status_code, 404)

    def test_adherence_reflects_real_logs_only(self):
        token = self._register().get_json()["token"]
        headers = self._auth_header(token)
        self._seed_two_logs(headers)

        response = self.client.get("/api/metrics/adherence", headers=headers)
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["real_log_count"], 2)
        self.assertIsNotNone(body["mean_intake_diff_kcal"])

    def test_gain_quality_without_logs_returns_404(self):
        token = self._register().get_json()["token"]
        response = self.client.get(
            "/api/metrics/gain-quality", headers=self._auth_header(token)
        )
        self.assertEqual(response.status_code, 404)

    def test_gain_quality_reflects_the_lean_fat_split_of_the_change(self):
        token = self._register().get_json()["token"]
        headers = self._auth_header(token)
        self._seed_two_logs(headers)

        response = self.client.get("/api/metrics/gain-quality", headers=headers)
        self.assertEqual(response.status_code, 200)
        rows = response.get_json()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["delta_lean_kg"], 0.0)
        self.assertEqual(rows[0]["delta_fat_kg"], 0.0)
        self.assertAlmostEqual(
            rows[1]["delta_lean_kg"] + rows[1]["delta_fat_kg"], 96.4 - 97.0, delta=0.02
        )
        self.assertAlmostEqual(rows[1]["fat_ratio_ideal"], 0.25)

    def test_energy_balance_without_logs_returns_404(self):
        token = self._register().get_json()["token"]
        response = self.client.get(
            "/api/metrics/energy-balance", headers=self._auth_header(token)
        )
        self.assertEqual(response.status_code, 404)

    def test_energy_balance_reflects_ingested_vs_tissue_surplus(self):
        token = self._register().get_json()["token"]
        headers = self._auth_header(token)
        self._seed_two_logs(headers)

        response = self.client.get("/api/metrics/energy-balance", headers=headers)
        self.assertEqual(response.status_code, 200)
        rows = response.get_json()
        self.assertEqual(len(rows), 2)
        self.assertIsNotNone(rows[0]["surplus_ingested_kcal"])
        self.assertIsNotNone(rows[0]["surplus_tissue_kcal"])
        self.assertIsNotNone(rows[0]["error_kcal"])
        # The most recent week has no *next* week's tissue change to compare yet.
        self.assertIsNone(rows[1]["surplus_tissue_kcal"])
        self.assertIsNone(rows[1]["error_kcal"])
        self.assertAlmostEqual(rows[0]["error_threshold_kcal"], 300.0)

    def test_increment_analytics_without_logs_returns_404(self):
        token = self._register().get_json()["token"]
        response = self.client.get(
            "/api/metrics/increment-analytics", headers=self._auth_header(token)
        )
        self.assertEqual(response.status_code, 404)

    def test_increment_analytics_skips_the_base_week_and_tracks_the_goal_rate(self):
        token = self._register().get_json()["token"]
        headers = self._auth_header(token)
        self._seed_two_logs(headers)

        response = self.client.get("/api/metrics/increment-analytics", headers=headers)
        self.assertEqual(response.status_code, 200)
        rows = response.get_json()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["date"], "2026-01-04")
        self.assertAlmostEqual(rows[0]["goal_weekly_rate"], -0.005)
        self.assertIsNotNone(rows[0]["deviation_pct"])

    def test_tef_without_logs_returns_404(self):
        token = self._register().get_json()["token"]
        response = self.client.get(
            "/api/metrics/tef", headers=self._auth_header(token)
        )
        self.assertEqual(response.status_code, 404)

    def test_tef_defaults_to_flat_with_no_macros_logged(self):
        token = self._register().get_json()["token"]
        headers = self._auth_header(token)
        self._seed_two_logs(headers)

        response = self.client.get("/api/metrics/tef", headers=headers)
        self.assertEqual(response.status_code, 200)
        rows = response.get_json()
        self.assertEqual(len(rows), 2)
        self.assertFalse(rows[0]["has_macros"])
        self.assertIsNone(rows[0]["tef_kcal_macros"])
        self.assertEqual(rows[0]["tef_mode_used"], "flat")
        self.assertGreater(rows[0]["tef_kcal_flat"], 0.0)

    def test_tef_breaks_down_a_macros_week_once_opted_in(self):
        token = self._register().get_json()["token"]
        headers = self._auth_header(token)
        self._seed_two_logs(headers)
        self.client.put(
            "/api/users/me/settings", json={"tef_mode": "macros"}, headers=headers
        )
        self.client.post(
            "/api/logs",
            json={
                "date": "2026-01-11",
                "weight_kg": 96.0,
                "waist_cm": 90.0,
                "neck_cm": 38.5,
                "intake_kcal": 2300.0,
                "steps": 6000,
                "carbs_g": 200.0,
                "fat_g": 70.0,
                "protein_g": 180.0,
            },
            headers=headers,
        )

        response = self.client.get("/api/metrics/tef", headers=headers)
        rows = response.get_json()
        macros_row = rows[-1]
        self.assertTrue(macros_row["has_macros"])
        self.assertEqual(macros_row["tef_mode_used"], "macros")
        self.assertAlmostEqual(
            macros_row["tef_kcal_macros"],
            0.300 * 200.0 + 0.135 * 70.0 + 1.000 * 180.0,
            delta=0.01,
        )

    def test_macro_targets_without_logs_returns_404(self):
        token = self._register().get_json()["token"]
        response = self.client.get(
            "/api/metrics/macro-targets", headers=self._auth_header(token)
        )
        self.assertEqual(response.status_code, 404)

    def test_macro_targets_reflects_default_g_per_kg_and_actual_when_logged(self):
        token = self._register().get_json()["token"]
        headers = self._auth_header(token)
        self._seed_two_logs(headers)

        response = self.client.get("/api/metrics/macro-targets", headers=headers)
        self.assertEqual(response.status_code, 200)
        rows = response.get_json()
        self.assertEqual(len(rows), 2)
        # First seeded log: weight 97.0 kg, defaults 1.75/0.70 g per kg.
        self.assertAlmostEqual(rows[0]["protein_target_g"], 1.75 * 97.0, delta=0.01)
        self.assertAlmostEqual(rows[0]["fat_target_g"], 0.70 * 97.0, delta=0.01)
        self.assertFalse(rows[0]["has_actual"])

        self.client.post(
            "/api/logs",
            json={
                "date": "2026-01-11",
                "weight_kg": 96.0,
                "waist_cm": 90.0,
                "neck_cm": 38.5,
                "intake_kcal": 2300.0,
                "steps": 6000,
                "carbs_g": 200.0,
                "fat_g": 70.0,
                "protein_g": 180.0,
            },
            headers=headers,
        )
        rows = self.client.get("/api/metrics/macro-targets", headers=headers).get_json()
        macros_row = rows[-1]
        self.assertTrue(macros_row["has_actual"])
        self.assertAlmostEqual(macros_row["protein_actual_kcal"], 180.0 * 4.0)

    def test_acknowledge_alert_removes_it_from_the_default_list(self):
        token = self._register().get_json()["token"]
        headers = self._auth_header(token)
        self.client.post(
            "/api/logs",
            json={
                "date": "2025-12-28",
                "weight_kg": 97.0,
                "waist_cm": 91.0,
                "neck_cm": 38.5,
                "intake_kcal": 2400.0,
                "steps": 6000,
            },
            headers=headers,
        )
        self.client.post(
            "/api/logs",
            json={
                "date": "2026-01-04",
                "weight_kg": 89.0,  # >8% down in one week
                "waist_cm": 89.0,
                "neck_cm": 38.0,
                "intake_kcal": 2000.0,
                "steps": 6000,
            },
            headers=headers,
        )

        alerts = self.client.get("/api/alerts", headers=headers).get_json()
        implausible = [a for a in alerts if a["type"] == "implausible_change"][0]
        self.assertIsNone(implausible["acknowledged_at"])

        ack_response = self.client.post(
            f"/api/alerts/{implausible['alert_id']}/acknowledge", headers=headers
        )
        self.assertEqual(ack_response.status_code, 200)
        self.assertIsNotNone(ack_response.get_json()["acknowledged_at"])

        after_default = self.client.get("/api/alerts", headers=headers).get_json()
        self.assertFalse(
            any(a["alert_id"] == implausible["alert_id"] for a in after_default)
        )

        after_all = self.client.get(
            "/api/alerts?include_acknowledged=true", headers=headers
        ).get_json()
        acked = [a for a in after_all if a["alert_id"] == implausible["alert_id"]]
        self.assertEqual(len(acked), 1)
        self.assertIsNotNone(acked[0]["acknowledged_at"])

    def test_acknowledge_alert_not_owned_by_user_returns_404(self):
        token_a = self._register().get_json()["token"]
        headers_a = self._auth_header(token_a)
        self.client.post(
            "/api/logs",
            json={
                "date": "2025-12-28",
                "weight_kg": 97.0,
                "waist_cm": 91.0,
                "neck_cm": 38.5,
                "intake_kcal": 2400.0,
                "steps": 6000,
            },
            headers=headers_a,
        )
        self.client.post(
            "/api/logs",
            json={
                "date": "2026-01-04",
                "weight_kg": 89.0,
                "waist_cm": 89.0,
                "neck_cm": 38.0,
                "intake_kcal": 2000.0,
                "steps": 6000,
            },
            headers=headers_a,
        )
        alerts = self.client.get("/api/alerts", headers=headers_a).get_json()
        alert_id = alerts[0]["alert_id"]

        token_b = self._register(
            username="other", email="other@example.com"
        ).get_json()["token"]
        headers_b = self._auth_header(token_b)
        response = self.client.post(
            f"/api/alerts/{alert_id}/acknowledge", headers=headers_b
        )
        self.assertEqual(response.status_code, 404)

    def test_report_includes_all_sections(self):
        token = self._register().get_json()["token"]
        headers = self._auth_header(token)
        self._seed_two_logs(headers)

        response = self.client.get("/api/users/me/report", headers=headers)
        self.assertEqual(response.status_code, 200)
        report = response.get_json()
        for key in (
            "profile",
            "latest_metrics",
            "adherence",
            "goal_history",
            "series",
            "alerts",
            "gain_quality",
            "energy_balance",
            "increment_analytics",
            "tef",
            "macro_targets",
            "generated_at",
        ):
            self.assertIn(key, report)
        self.assertEqual(len(report["series"]), 2)
        self.assertIsNotNone(report["latest_metrics"])
        self.assertEqual(len(report["gain_quality"]), 2)
        self.assertEqual(len(report["energy_balance"]), 2)
        self.assertEqual(len(report["tef"]), 2)
        self.assertEqual(len(report["macro_targets"]), 2)
        # Only one real week-over-week increment exists for a 2-log series.
        self.assertEqual(len(report["increment_analytics"]), 1)
        self.assertEqual(len(report["goal_history"]), 1)

    def test_settings_default_before_any_override(self):
        token = self._register().get_json()["token"]
        response = self.client.get(
            "/api/users/me/settings", headers=self._auth_header(token)
        )
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertTrue(body["is_default"])
        self.assertEqual(body["stagnation_weeks"], 3)
        self.assertEqual(body["bmr_model"], "cunningham")
        self.assertAlmostEqual(body["w_rfm"], 0.50)
        self.assertAlmostEqual(body["ffmi_coef"], 6.3)

    def test_settings_update_and_history(self):
        token = self._register().get_json()["token"]
        headers = self._auth_header(token)

        update_response = self.client.put(
            "/api/users/me/settings",
            json={"stagnation_weeks": 2, "significant_deviation_kg": 0.5},
            headers=headers,
        )
        self.assertEqual(update_response.status_code, 200)
        body = update_response.get_json()
        self.assertFalse(body["is_default"])
        self.assertEqual(body["stagnation_weeks"], 2)
        self.assertEqual(body["significant_deviation_kg"], 0.5)

        get_response = self.client.get("/api/users/me/settings", headers=headers)
        self.assertEqual(get_response.get_json()["stagnation_weeks"], 2)

        history_response = self.client.get(
            "/api/users/me/settings/history", headers=headers
        )
        self.assertEqual(len(history_response.get_json()), 1)

    def test_settings_update_rejects_invalid_value(self):
        token = self._register().get_json()["token"]
        response = self.client.put(
            "/api/users/me/settings",
            json={"tef": 1.5},
            headers=self._auth_header(token),
        )
        self.assertEqual(response.status_code, 400)

    def test_settings_update_bmr_model_and_bf_weights(self):
        token = self._register().get_json()["token"]
        headers = self._auth_header(token)

        response = self.client.put(
            "/api/users/me/settings",
            json={"bmr_model": "mifflin", "w_rfm": 0.6, "w_navy": 0.2, "w_deur": 0.2},
            headers=headers,
        )
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["bmr_model"], "mifflin")
        self.assertAlmostEqual(body["w_rfm"], 0.6)

    def test_settings_update_rejects_bf_weights_not_summing_to_one(self):
        token = self._register().get_json()["token"]
        response = self.client.put(
            "/api/users/me/settings",
            json={"w_rfm": 0.6, "w_navy": 0.3, "w_deur": 0.3},
            headers=self._auth_header(token),
        )
        self.assertEqual(response.status_code, 400)

    def test_settings_update_rejects_invalid_bmr_model(self):
        token = self._register().get_json()["token"]
        response = self.client.put(
            "/api/users/me/settings",
            json={"bmr_model": "not_a_model"},
            headers=self._auth_header(token),
        )
        self.assertEqual(response.status_code, 400)

    def test_settings_update_reconciliation_error_threshold(self):
        token = self._register().get_json()["token"]
        headers = self._auth_header(token)

        get_response = self.client.get("/api/users/me/settings", headers=headers)
        self.assertAlmostEqual(
            get_response.get_json()["reconciliation_error_threshold_kcal"], 300.0
        )

        update_response = self.client.put(
            "/api/users/me/settings",
            json={"reconciliation_error_threshold_kcal": 150.0},
            headers=headers,
        )
        self.assertEqual(update_response.status_code, 200)
        self.assertAlmostEqual(
            update_response.get_json()["reconciliation_error_threshold_kcal"], 150.0
        )

    def test_settings_update_tef_mode_and_kappas(self):
        token = self._register().get_json()["token"]
        headers = self._auth_header(token)

        get_response = self.client.get("/api/users/me/settings", headers=headers)
        default_body = get_response.get_json()
        self.assertEqual(default_body["tef_mode"], "flat")
        self.assertAlmostEqual(default_body["kappa_carbs"], 0.300)
        self.assertAlmostEqual(default_body["kappa_fat"], 0.135)
        self.assertAlmostEqual(default_body["kappa_protein"], 1.000)
        self.assertAlmostEqual(default_body["macro_kcal_mismatch_pct"], 0.15)

        update_response = self.client.put(
            "/api/users/me/settings",
            json={"tef_mode": "macros", "kappa_protein": 0.95},
            headers=headers,
        )
        self.assertEqual(update_response.status_code, 200)
        body = update_response.get_json()
        self.assertEqual(body["tef_mode"], "macros")
        self.assertAlmostEqual(body["kappa_protein"], 0.95)

    def test_settings_update_rejects_invalid_tef_mode(self):
        token = self._register().get_json()["token"]
        response = self.client.put(
            "/api/users/me/settings",
            json={"tef_mode": "not_a_mode"},
            headers=self._auth_header(token),
        )
        self.assertEqual(response.status_code, 400)

    def test_settings_update_macro_targets(self):
        token = self._register().get_json()["token"]
        headers = self._auth_header(token)

        get_response = self.client.get("/api/users/me/settings", headers=headers)
        default_body = get_response.get_json()
        self.assertAlmostEqual(default_body["protein_target_g_per_kg"], 1.75)
        self.assertAlmostEqual(default_body["fat_target_g_per_kg"], 0.70)
        self.assertAlmostEqual(default_body["macro_target_deviation_pct"], 0.20)

        update_response = self.client.put(
            "/api/users/me/settings",
            json={"protein_target_g_per_kg": 2.0, "fat_target_g_per_kg": 0.9},
            headers=headers,
        )
        self.assertEqual(update_response.status_code, 200)
        body = update_response.get_json()
        self.assertAlmostEqual(body["protein_target_g_per_kg"], 2.0)
        self.assertAlmostEqual(body["fat_target_g_per_kg"], 0.9)

    def test_out_of_range_bulk_rate_produces_a_dismissible_alert(self):
        token = self._register().get_json()["token"]
        headers = self._auth_header(token)
        self.client.put(
            "/api/users/me", json={"weekly_rate": 0.02}, headers=headers
        )
        alerts = self.client.get("/api/alerts", headers=headers).get_json()
        bulk_alerts = [a for a in alerts if a["type"] == "bulk_rate_out_of_range"]
        self.assertEqual(len(bulk_alerts), 1)

        ack_response = self.client.post(
            f"/api/alerts/{bulk_alerts[0]['alert_id']}/acknowledge", headers=headers
        )
        self.assertEqual(ack_response.status_code, 200)
        remaining = self.client.get("/api/alerts", headers=headers).get_json()
        self.assertFalse(any(a["type"] == "bulk_rate_out_of_range" for a in remaining))

    def test_custom_alert_threshold_changes_detection(self):
        token = self._register().get_json()["token"]
        headers = self._auth_header(token)
        self._seed_two_logs(headers)
        # Default significant_deviation_kg is 1.0; a small ~0.5kg gap
        # shouldn't trip it, but a tightened 0.1kg threshold should.
        self.client.post(
            "/api/logs",
            json={
                "date": "2026-01-11",
                "weight_kg": 96.0,
                "waist_cm": 90.0,
                "neck_cm": 38.5,
                "intake_kcal": 2300.0,
                "steps": 6000,
            },
            headers=headers,
        )
        default_alerts = self.client.get("/api/alerts", headers=headers).get_json()
        self.assertFalse(any(a["type"] == "deviation" for a in default_alerts))

        self.client.put(
            "/api/users/me/settings",
            json={"significant_deviation_kg": 0.1},
            headers=headers,
        )
        tightened_alerts = self.client.get("/api/alerts", headers=headers).get_json()
        self.assertTrue(any(a["type"] == "deviation" for a in tightened_alerts))

    def test_reset_password_unknown_identifier_returns_404(self):
        response = self.client.post(
            "/api/auth/reset-password",
            json={"identifier": "no-such-user", "new_password": "whatever12"},
        )
        self.assertEqual(response.status_code, 404)

    def test_reset_password_directly_resets_with_no_verification(self):
        self._register()

        reset_response = self.client.post(
            "/api/auth/reset-password",
            json={"identifier": "demo_cut", "new_password": "brand-new-password-1"},
        )
        self.assertEqual(reset_response.status_code, 200)
        self.assertIn("message", reset_response.get_json())

        relogin = self.client.post(
            "/api/auth/login", json={"username": "demo_cut", "password": "brand-new-password-1"}
        )
        self.assertEqual(relogin.status_code, 200)

    def test_reset_password_requires_both_fields(self):
        response = self.client.post(
            "/api/auth/reset-password", json={"identifier": "demo_cut"}
        )
        self.assertEqual(response.status_code, 400)

    def test_projection_activity_query_param_is_accepted(self):
        token = self._register().get_json()["token"]
        headers = self._auth_header(token)
        self._seed_two_logs(headers)

        response = self.client.get(
            "/api/projection?weeks=2&activity=trend", headers=headers
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.get_json()), 2)

    def test_save_projection_persists_activity_model(self):
        token = self._register().get_json()["token"]
        headers = self._auth_header(token)
        self._seed_two_logs(headers)

        response = self.client.post(
            "/api/projection?weeks=2", json={"activity": "trend"}, headers=headers
        )
        self.assertEqual(response.status_code, 201)
        rows = response.get_json()["rows"]
        self.assertTrue(all(row["activity_model"] == "trend" for row in rows))

    def test_alert_history_includes_acknowledged_alerts(self):
        token = self._register().get_json()["token"]
        headers = self._auth_header(token)
        self.client.post(
            "/api/logs",
            json={
                "date": "2025-12-28",
                "weight_kg": 97.0,
                "waist_cm": 91.0,
                "neck_cm": 38.5,
                "intake_kcal": 2400.0,
                "steps": 6000,
            },
            headers=headers,
        )
        self.client.post(
            "/api/logs",
            json={
                "date": "2026-01-04",
                "weight_kg": 89.0,  # implausible swing
                "waist_cm": 89.0,
                "neck_cm": 38.0,
                "intake_kcal": 2000.0,
                "steps": 6000,
            },
            headers=headers,
        )
        # This scenario trips both the implausible-change and deviation
        # detectors -- acknowledge everything currently open.
        open_alerts = self.client.get("/api/alerts", headers=headers).get_json()
        self.assertGreaterEqual(len(open_alerts), 1)
        for alert in open_alerts:
            self.client.post(
                f"/api/alerts/{alert['alert_id']}/acknowledge", headers=headers
            )

        default_view = self.client.get("/api/alerts", headers=headers).get_json()
        self.assertEqual(default_view, [])

        full_history = self.client.get(
            "/api/alerts?include_acknowledged=true", headers=headers
        ).get_json()
        self.assertEqual(len(full_history), len(open_alerts))
        self.assertTrue(all(a["acknowledged_at"] is not None for a in full_history))


if __name__ == "__main__":
    unittest.main()
