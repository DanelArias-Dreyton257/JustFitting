import unittest

from server.src.api.app import create_app


class ApiTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app({"DB_PATH": ":memory:", "TESTING": True})
        self.client = self.app.test_client()

    def tearDown(self):
        self.app.extensions["db"].close()

    def _register(
        self, username="danel", email="danel@example.com", password="hunter22"
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
            "/api/auth/login", json={"username": "danel", "password": "hunter22"}
        )
        self.assertEqual(login_response.status_code, 200)
        login_token = login_response.get_json()["token"]

        me_response = self.client.get(
            "/api/users/me", headers=self._auth_header(login_token)
        )
        self.assertEqual(me_response.status_code, 200)
        self.assertEqual(me_response.get_json()["username"], "danel")

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
            "/api/auth/login", json={"username": "danel", "password": "new-password-1"}
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

    def test_alerts_empty_without_logs(self):
        token = self._register().get_json()["token"]
        response = self.client.get("/api/alerts", headers=self._auth_header(token))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), [])

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


if __name__ == "__main__":
    unittest.main()
