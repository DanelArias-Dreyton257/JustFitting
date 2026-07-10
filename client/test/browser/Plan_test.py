"""Playwright browser tests for the Plan tab's Phase 8 additions --
retroactively editing the active goal's start date (8.1) and the
target-BF/weekly-rate coherence check (8.2) -- drives the real client app
(client.src.Client.create_client_app) against a real, in-process Flask API,
same harness as Account_test.py/Log_test.py.
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


class PlanTest(unittest.TestCase):
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
        self._register_and_log_in(f"plantester_{self._testMethodName}")

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

    def _log_a_real_week(self):
        """Logs one real week via the Log view's wizard -- gives the
        account a computable current body fat so Phase 8.2's coherence
        check has something to compare against."""
        self._navigate("log")
        self.page.fill('#log-form [name="weight_kg"]', "96.4")
        self.page.click("#log-next")
        self.page.fill('#log-form [name="waist_cm"]', "90.5")
        self.page.fill('#log-form [name="neck_cm"]', "38.5")
        self.page.click("#log-next")
        self.page.fill('#log-form [name="intake_kcal"]', "2350")
        self.page.fill('#log-form [name="steps"]', "6200")
        self.page.click("#log-next")
        self.page.click("#log-save")
        self.page.wait_for_selector("#log-table tbody tr")

    def test_goal_start_date_defaults_to_today_and_is_editable(self):
        today_iso = datetime.date.today().isoformat()
        self._navigate("plan")
        self.page.wait_for_function(
            "document.getElementById('goal-start-date-section').hidden === false"
        )
        self.assertEqual(
            self.page.eval_on_selector("#goal-start-date-input", "el => el.value"),
            today_iso,
        )

        backdated = (datetime.date.today() - datetime.timedelta(days=60)).isoformat()
        self.page.fill("#goal-start-date-input", backdated)
        self.page.click("#goal-start-date-form button[type=submit]")
        self.page.wait_for_function(
            f"document.getElementById('goal-start-date-input').value === '{backdated}'"
        )

        # Persisted server-side, not just left in the form's local state.
        self.page.reload()
        self._navigate("plan")
        self.page.wait_for_function(
            f"document.getElementById('goal-start-date-input').value === '{backdated}'"
        )
        row_text = self.page.inner_text("#goal-history-table tbody tr")
        self.assertIn(backdated, row_text)

    def test_goal_start_date_rejects_a_future_date(self):
        # The client sets the date input's own `max` to today (mirroring
        # GoalPlanManager.update_start_date's server-side bound), so a
        # future value is caught by native HTML5 validation before the
        # form's submit handler -- and thus the server -- ever sees it.
        self._navigate("plan")
        self.page.wait_for_function(
            "document.getElementById('goal-start-date-section').hidden === false"
        )
        future = (datetime.date.today() + datetime.timedelta(days=30)).isoformat()
        self.page.fill("#goal-start-date-input", future)
        is_valid = self.page.eval_on_selector(
            "#goal-start-date-input", "el => el.checkValidity()"
        )
        self.assertFalse(is_valid)

    def test_incoherent_plan_preview_shows_an_inline_error(self):
        self._log_a_real_week()
        self._navigate("plan")
        self.page.wait_for_function(
            "document.querySelector('#plan-form [name=\"target_bf_pct\"]').value !== ''"
        )
        # The logged week's real body fat is well above 15% -- pairing that
        # cut target with a positive (bulk) weekly rate is incoherent.
        self.page.fill('#plan-form [name="target_bf_pct"]', "15")
        self.page.fill('#plan-form [name="weekly_rate_pct"]', "0.5")
        self.page.click('#plan-form button[type=submit]')
        self.page.wait_for_function(
            "document.querySelector('.form-error[data-for=\"plan-form\"]').textContent !== ''"
        )
        self.assertTrue(self.page.is_hidden("#plan-preview-result"))

    def test_coherent_plan_preview_still_works(self):
        self._log_a_real_week()
        self._navigate("plan")
        self.page.wait_for_function(
            "document.querySelector('#plan-form [name=\"target_bf_pct\"]').value !== ''"
        )
        self.page.fill('#plan-form [name="target_bf_pct"]', "15")
        self.page.fill('#plan-form [name="weekly_rate_pct"]', "-0.5")
        self.page.click('#plan-form button[type=submit]')
        self.page.wait_for_selector("#plan-preview-result:not([hidden])")


if __name__ == "__main__":
    unittest.main()
