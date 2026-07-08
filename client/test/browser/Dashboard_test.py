"""Playwright browser tests for the simplified dashboard-as-home summary
(Phase 4.2) -- drives the real client app (client.src.Client.create_client_app)
against a real, in-process Flask API, so this exercises the actual shipped
app.js/views.js/index.html/style.css, not a fixture.
"""

import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from playwright.sync_api import sync_playwright

from client.src.Client import create_client_app
from client.test.browser.live_server import LiveServer
from server.src.api.app import create_app


def _register_payload(username: str) -> dict:
    return {
        "username": username,
        "email": f"{username}@example.com",
        "password": "s3cret123",
        "height_cm": "176",
        "sex": "1",
        "birthdate": "2001-08-22",
    }


class DashboardTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db_dir = tempfile.mkdtemp(prefix="justfitting-browser-test-")
        cls.db_path = str(Path(cls.db_dir) / "browser_test.db")

        api_app = create_app({"DB_PATH": cls.db_path, "CORS_ORIGINS": "*"})
        cls.api_server = LiveServer(api_app)
        cls.api_server.start()

        cls._prev_api_base_url = os.environ.get("JUSTFITTING_API_BASE_URL")
        os.environ["JUSTFITTING_API_BASE_URL"] = cls.api_server.url

        cls.client_server = LiveServer(create_client_app())
        cls.client_server.start()

        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        cls.client_server.stop()
        cls.api_server.stop()
        if cls._prev_api_base_url is None:
            os.environ.pop("JUSTFITTING_API_BASE_URL", None)
        else:
            os.environ["JUSTFITTING_API_BASE_URL"] = cls._prev_api_base_url
        shutil.rmtree(cls.db_dir, ignore_errors=True)

    def setUp(self):
        self.page = self.browser.new_page()
        self.page.goto(self.client_server.url)
        self._register_and_log_in(f"dashtester_{self._testMethodName}")

    def tearDown(self):
        self.page.close()

    def _register_and_log_in(self, username: str):
        for field, value in _register_payload(username).items():
            locator = self.page.locator(f'#register-form [name="{field}"]')
            if locator.evaluate("el => el.tagName") == "SELECT":
                locator.select_option(value)
            else:
                locator.fill(value)
        self.page.click("#register-form button[type=submit]")
        self.page.wait_for_selector("#view-dashboard:not([hidden])")

    def _navigate(self, view: str):
        self.page.click("#nav-toggle")
        self.page.click(f'.nav-link[data-view="{view}"]')
        self.page.wait_for_selector(f"#view-{view}:not([hidden])")

    def _log_week(self, date: str, weight_kg: float):
        self._navigate("log")
        # Phase 4.4: the wizard's date is derived from the Log view's
        # day/week navigator (a hidden input), not a directly-editable
        # field -- jump the navigator's date-picker there first.
        self.page.eval_on_selector(
            "#log-nav-date",
            "(el, value) => { el.value = value; el.dispatchEvent(new Event('change')); }",
            date,
        )
        self.page.fill('#log-form [name="weight_kg"]', str(weight_kg))
        self.page.click("#log-next")
        self.page.fill('#log-form [name="waist_cm"]', "80")
        self.page.fill('#log-form [name="neck_cm"]', "35")
        self.page.click("#log-next")
        self.page.fill('#log-form [name="intake_kcal"]', "2000")
        self.page.fill('#log-form [name="steps"]', "5000")
        self.page.click("#log-next")
        self.page.click("#log-save")
        self.page.wait_for_selector(f'#log-table tbody tr td:text-is("{date}")')

    def _go_to_dashboard(self):
        self._navigate("dashboard")

    def test_summary_sections_render_without_expanding_charts(self):
        self._log_week("2026-06-01", 90.0)
        self._log_week("2026-06-08", 89.0)
        self._go_to_dashboard()

        self.page.wait_for_selector("#summary-weight-stats .stat-tile")
        # `.stat-tile .label` is rendered all-caps via CSS text-transform,
        # so compare case-insensitively rather than against the source casing.
        weight_text = self.page.inner_text("#summary-weight-stats").lower()
        self.assertIn("weight", weight_text)
        self.assertIn("body fat", weight_text)
        self.assertIn("lean mass", weight_text)
        # A second logged week should surface a change vs the previous one.
        self.assertIn("kg", self.page.inner_text("#summary-weight-stats .delta"))

        calories_text = self.page.inner_text("#summary-calories-stats").lower()
        self.assertIn("target calories", calories_text)
        self.assertIn("tdee", calories_text)

        goal_text = self.page.inner_text("#summary-goal-stats").lower()
        self.assertIn("weeks to goal", goal_text)
        self.assertIn("target body fat", goal_text)
        self.assertIn("target weight", goal_text)
        self.assertIn("keep lean", goal_text)
        # A goal not yet reached should surface an arrowed "to goal" delta.
        self.assertIn("to goal", goal_text)

    def test_chart_grid_is_collapsed_and_lazy_loaded(self):
        self._log_week("2026-06-01", 90.0)
        self._go_to_dashboard()

        self.assertIsNone(self.page.get_attribute("#dashboard-details", "open"))
        self.assertEqual(
            self.page.eval_on_selector("#chart-weight", "el => el.childElementCount"), 0
        )

        self.page.click("#dashboard-details > summary")
        self.page.wait_for_function(
            "document.getElementById('chart-weight').childElementCount > 0"
        )
        self.assertIsNotNone(self.page.get_attribute("#dashboard-details", "open"))

    def test_projection_toggle_overlays_forecast_and_marker(self):
        # Projection.project_series_with_inputs needs >= 2 real logs to fit
        # a trend, so two weeks are logged before expanding the charts.
        self._log_week("2026-06-01", 90.0)
        self._log_week("2026-06-08", 89.0)
        self._go_to_dashboard()
        self.page.click("#dashboard-details > summary")
        self.page.wait_for_function(
            "document.getElementById('chart-weight').childElementCount > 0"
        )

        def weight_points():
            return self.page.eval_on_selector_all("#chart-weight circle", "els => els.length")

        def marker_lines():
            return self.page.eval_on_selector_all(
                "#chart-weight .chart-marker-line", "els => els.length"
            )

        base_count = weight_points()
        self.assertEqual(base_count, 2)
        self.assertEqual(marker_lines(), 0)

        self.page.check("#dashboard-projection-toggle")
        self.page.wait_for_function(
            f"document.querySelectorAll('#chart-weight circle').length > {base_count}"
        )
        # Default forecast window is 4 weeks appended past the 2 real logs.
        self.assertEqual(weight_points(), base_count + 4)
        self.assertEqual(marker_lines(), 1)

        self.page.select_option("#dashboard-projection-weeks", "8")
        self.page.wait_for_function(
            f"document.querySelectorAll('#chart-weight circle').length === {base_count + 8}"
        )

        self.page.uncheck("#dashboard-projection-toggle")
        self.page.wait_for_function(
            f"document.querySelectorAll('#chart-weight circle').length === {base_count}"
        )
        self.assertEqual(marker_lines(), 0)

    def test_goal_trajectory_marker_excludes_a_future_dated_goal_change(self):
        # Every account's initial goal plan is start_date=today (real wall-
        # clock date), which -- unlike the fixed 2026-06-xx log dates used
        # throughout this suite -- can land after the last logged week. That
        # goal-change marker used to be silently clamped to the chart's
        # right edge (off the real-only date domain); once the projection
        # toggle widens the domain, it must not reappear mid-chart as a
        # second, unrelated marker alongside "Last logged".
        self._log_week("2026-06-01", 90.0)
        self._log_week("2026-06-08", 89.0)
        self._go_to_dashboard()
        self.page.click("#dashboard-details > summary")
        self.page.wait_for_function(
            "document.getElementById('chart-weight').childElementCount > 0"
        )

        self.page.check("#dashboard-projection-toggle")
        self.page.wait_for_function(
            "document.querySelectorAll('#chart-weight circle').length > 2"
        )

        marker_titles = self.page.eval_on_selector_all(
            "#chart-goal-trajectory .chart-marker-line title", "els => els.map(e => e.textContent)"
        )
        self.assertEqual(marker_titles, ["Last logged"])

    def _target_weight_kg(self):
        text = self.page.locator(
            "#summary-goal-stats .stat-tile", has_text="Target weight"
        ).locator(".value").inner_text()
        return float(text.replace(" kg", "").strip())

    def _target_weight_delta_kg(self):
        text = self.page.locator(
            "#summary-goal-stats .stat-tile", has_text="Target weight"
        ).locator(".delta").inner_text()
        match = re.search(r"(-?\d+\.\d+)\s*kg to goal", text)
        return float(match.group(1))

    def _wait_for_weight_value(self, expected_prefix):
        # The Weight tile and the Weight-to-goal tile are rendered together
        # from the same fetch, so waiting for the former to reflect the new
        # weight is a reliable signal the latter has refreshed too --
        # `.stat-tile` already exists in the DOM from the previous render
        # (only its content changes), so waiting on its mere presence would
        # race the fetch and read stale content.
        self.page.wait_for_function(
            "expected => document.querySelector('#summary-weight-stats .stat-tile .value')"
            "?.innerText.trim().startsWith(expected)",
            arg=expected_prefix,
        )

    def _fetch_metrics_latest(self):
        return self.page.evaluate(
            """async () => {
                const token = localStorage.getItem('justfitting.token');
                const res = await fetch(
                    `${window.JUSTFITTING_API_BASE_URL}/api/metrics/latest`,
                    { headers: { Authorization: `Bearer ${token}` } }
                );
                return res.json();
            }"""
        )

    def test_target_weight_tile_shows_goal_weight_and_remaining_distance_delta(self):
        # Phase 5.5's bug: "Weight to goal" used to read weight_to_shed_kg
        # (this week's incremental target change), which for a steady weekly
        # rate is always roughly the same small figure regardless of how
        # close the goal actually is, rather than the actual remaining
        # distance to final_weight_kg. Phase 5.9 then flipped the tile to
        # lead with the target weight itself, with the remaining distance
        # as an arrowed subtitle -- verify both halves against the API.
        self._log_week("2026-06-01", 95.0)
        self._go_to_dashboard()
        self._wait_for_weight_value("95.0")
        metrics = self._fetch_metrics_latest()
        current_weight = metrics["fat_mass_kg"] + metrics["lean_mass_kg"]
        expected_target_weight = metrics["final_weight_kg"]
        expected_remaining = expected_target_weight - current_weight
        # The pre-fix figure (weight_to_shed_kg) would have been ~0.45-0.5kg
        # here regardless of proximity to goal -- assert the fix isn't that.
        self.assertNotAlmostEqual(
            abs(metrics["weight_to_shed_kg"]), abs(expected_remaining), places=1
        )
        self.assertAlmostEqual(self._target_weight_kg(), expected_target_weight, places=1)
        self.assertAlmostEqual(self._target_weight_delta_kg(), expected_remaining, places=1)

    def test_calories_summary_has_subtitles_and_logged_intake_tile(self):
        self._log_week("2026-06-01", 90.0)
        self._go_to_dashboard()
        self.page.wait_for_selector("#summary-calories-stats .stat-tile")
        calories_text = self.page.inner_text("#summary-calories-stats").lower()
        self.assertIn("what to eat", calories_text)
        self.assertIn("estimated calories burned", calories_text)
        self.assertIn("actual vs target/day", calories_text)
        self.assertIn("this week's intake", calories_text)
        # This week's intake tile comes before Adherence.
        self.assertLess(
            calories_text.index("this week's intake"), calories_text.index("adherence")
        )
        # _log_week logs intake_kcal=2000.
        self.assertIn("2000 kcal", calories_text)

    def test_unconfigured_goal_alert_shows_for_a_fresh_account_and_is_dismissible(self):
        # Phase 5.2 follow-up: a brand-new account's auto-assigned default
        # goal (0% weekly rate) surfaces a reminder to visit the Plan tab --
        # even before any log exists, via the same alerts panel/dismiss
        # flow every other alert already uses.
        self._go_to_dashboard()
        self.page.wait_for_selector("#dashboard-alerts .alert-item")
        self.assertEqual(
            self.page.get_attribute("#dashboard-alerts .alert-item", "data-type"),
            "unconfigured_goal",
        )

        self.page.click("#dashboard-alerts .alert-dismiss-btn")
        self.page.wait_for_function(
            "document.querySelectorAll('#dashboard-alerts .alert-item').length === 0"
        )

    def test_dashboard_with_no_logs_shows_placeholders_not_errors(self):
        # A brand-new account has no logs yet -- summary sections should
        # degrade to a friendly message instead of throwing on null metrics.
        self._go_to_dashboard()
        self.page.wait_for_selector("#summary-weight-stats .disclaimer")
        self.assertIn("Log a week", self.page.inner_text("#summary-weight-stats"))
        self.assertIn("Log a week", self.page.inner_text("#summary-calories-stats"))
        self.assertIn("Log a week", self.page.inner_text("#summary-goal-stats"))


if __name__ == "__main__":
    unittest.main()
