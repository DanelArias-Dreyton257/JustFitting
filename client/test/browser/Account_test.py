"""Playwright browser tests for the Account view (Phase 5.8: profile-only,
goal editing lives solely in the Plan tab) -- drives the real client app
(client.src.Client.create_client_app) against a real, in-process Flask API,
same harness as Dashboard_test.py/Log_test.py.
"""

import datetime
import os
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


class AccountTest(unittest.TestCase):
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
        self._register_and_log_in(f"accounttester_{self._testMethodName}")

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

    def test_register_form_has_no_goal_fields_and_registration_succeeds(self):
        # Registration in setUp() already succeeded through a form with no
        # goal fields -- confirm they're genuinely absent from the DOM, not
        # just skipped by the payload helper above.
        self.assertEqual(self.page.locator('#register-form [name="target_bf_pct"]').count(), 0)
        self.assertEqual(self.page.locator('#register-form [name="weekly_rate_pct"]').count(), 0)

    def test_profile_form_has_no_goal_fields(self):
        self._navigate("account")
        self.assertEqual(self.page.locator('#profile-form [name="target_bf_pct"]').count(), 0)
        self.assertEqual(self.page.locator('#profile-form [name="weekly_rate_pct"]').count(), 0)
        self.assertEqual(self.page.inner_text("#profile-form h2"), "Profile")

    def test_editing_profile_fields_round_trips_without_touching_the_active_goal(self):
        self._navigate("plan")
        # refreshPlan() populates the form asynchronously after navigation
        # reveals the view -- wait for it rather than racing the fetch.
        self.page.wait_for_function(
            "document.querySelector('#plan-form [name=\"target_bf_pct\"]').value !== ''"
        )
        target_bf_before = self.page.eval_on_selector(
            '#plan-form [name="target_bf_pct"]', "el => el.value"
        )
        weekly_rate_before = self.page.eval_on_selector(
            '#plan-form [name="weekly_rate_pct"]', "el => el.value"
        )

        self._navigate("account")
        self.page.fill('#profile-form [name="height_cm"]', "180")
        self.page.select_option('#profile-form [name="sex"]', "0")
        self.page.fill('#profile-form [name="birthdate"]', "1995-01-01")
        self.page.click('#profile-form button[type=submit]')
        self.page.wait_for_function(
            "document.querySelector('#profile-form [name=\"height_cm\"]').value === '180'"
        )

        # Reload from the server to prove the edit actually persisted, not
        # just left in the form's local state.
        self.page.reload()
        self._navigate("account")
        self.page.wait_for_function(
            "document.querySelector('#profile-form [name=\"height_cm\"]').value === '180'"
        )
        self.assertEqual(
            self.page.eval_on_selector('#profile-form [name="sex"]', "el => el.value"), "0"
        )
        self.assertEqual(
            self.page.eval_on_selector('#profile-form [name="birthdate"]', "el => el.value"),
            "1995-01-01",
        )

        self._navigate("plan")
        self.page.wait_for_function(
            "document.querySelector('#plan-form [name=\"target_bf_pct\"]').value !== ''"
        )
        self.assertEqual(
            self.page.eval_on_selector('#plan-form [name="target_bf_pct"]', "el => el.value"),
            target_bf_before,
        )
        self.assertEqual(
            self.page.eval_on_selector('#plan-form [name="weekly_rate_pct"]', "el => el.value"),
            weekly_rate_before,
        )

    def _mock_health_sync_plugin(self):
        # Mirrors HealthSync_test.py's own mock, but also records the
        # sinceDate a "Sync now" press actually requests, so this test can
        # confirm the requested window isn't silently clamped -- the real
        # regression: a stale 90-day ceiling (things-to-improve.txt) left
        # over from before READ_HEALTH_DATA_HISTORY existed (README's Phase
        # 7.6) meant a >90-day request never reached the native plugin at
        # all, regardless of what the user typed.
        self.page.evaluate(
            """() => {
                window.__syncCalls = [];
                window.Capacitor = {
                    Plugins: {
                        HealthSync: {
                            isAvailable: async () => ({ available: true, status: "available" }),
                            hasPermissions: async () => ({ steps: true, nutrition: true, granted: true }),
                            requestPermissions: async () => ({ granted: true }),
                            readRecentReadings: async ({ sinceDate }) => {
                                window.__syncCalls.push(sinceDate);
                                return { readings: [] };
                            },
                        },
                    },
                };
            }"""
        )

    def test_health_sync_window_input_allows_more_than_90_days(self):
        self._mock_health_sync_plugin()
        self._navigate("account")
        self.page.wait_for_selector("#health-sync-section:not([hidden])")
        self.assertEqual(
            self.page.get_attribute("#health-sync-days-input", "max"), "365"
        )

        self.page.fill("#health-sync-days-input", "200")
        self.page.click("#health-sync-now-btn")
        self.page.wait_for_function("window.__syncCalls && window.__syncCalls.length === 1")
        requested_since_date = self.page.evaluate("window.__syncCalls[0]")

        today = self.page.evaluate(
            "() => { const d = new Date(); "
            "return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-"
            "${String(d.getDate()).padStart(2, '0')}`; }"
        )
        expected_since_date = (
            datetime.date.fromisoformat(today) - datetime.timedelta(days=200)
        ).isoformat()
        # A pre-fix 90-day clamp would have requested a since-date only 90
        # days back, well after this expectation -- asserting equality (not
        # just "further back than 90 days") pins the exact requested window.
        self.assertEqual(requested_since_date, expected_since_date)


if __name__ == "__main__":
    unittest.main()
