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
        """Logs one real week via the Log view's wizard, plus a matching
        body_measurements row via the Body view -- gives the account a
        computable current body fat so Phase 8.2's coherence check has
        something to compare against (Phase 9.1: waist/neck are resolved
        from body_measurements, no longer part of the Log wizard itself)."""
        today_iso = datetime.date.today().isoformat()
        self._log_a_measurement(today_iso)

        self._navigate("log")
        self.page.fill('#log-form [name="weight_kg"]', "96.4")
        self.page.click("#log-next")
        self.page.fill('#log-form [name="intake_kcal"]', "2350")
        self.page.fill('#log-form [name="steps"]', "6200")
        self.page.click("#log-next")
        self.page.click("#log-save")
        self.page.wait_for_selector("#log-table tbody tr")

    def _log_a_measurement(self, iso_date: str, waist_cm: float = 90.5, neck_cm: float = 38.5):
        # Navigating to Body kicks off an async refreshBody() (fetch +
        # form-defaults reset, including resetting the date input to today)
        # that isn't awaited by the click handler -- waiting on the view
        # becoming visible alone races that reset, which can otherwise
        # clobber the date this method is about to fill in. Waiting for the
        # GET it triggers to complete closes that race.
        self.page.click("#nav-toggle")
        with self.page.expect_response(
            lambda r: "/api/body-measurements" in r.url and r.request.method == "GET"
        ):
            self.page.click('.nav-link[data-view="body"]')
        self.page.wait_for_selector("#view-body:not([hidden])")
        self.page.fill("#body-date-input", iso_date)
        self.page.fill('#body-form [name="waist_cm"]', str(waist_cm))
        self.page.fill('#body-form [name="neck_cm"]', str(neck_cm))
        self.page.click("#body-save")
        self.page.wait_for_selector(f'#body-table tbody tr td:text-is("{iso_date}")')

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

    def test_weekly_rate_field_accepts_a_typed_minus_sign(self):
        # things-to-improve.txt: on Android, weekly_rate_pct's virtual
        # keyboard offered no "-" key at all when the field was
        # type="number" (a real, widely-reported Chromium/WebView
        # limitation for numeric inputs, not fixable via min/max/step) --
        # fixed by switching to type="text" + inputmode="decimal" +
        # pattern, which Android's decimal keyboard does show a minus key
        # for. Playwright's fill() sets the DOM value directly and can't
        # reproduce a real device's virtual-keyboard layout either way, so
        # this asserts the field's actual attributes (the real fix) and
        # drives it via press_sequentially (real per-character key events,
        # unlike fill()) to prove nothing in this app's own JS -- as
        # opposed to the OS keyboard -- blocks a "-" keystroke.
        field = self.page.locator('#plan-form [name="weekly_rate_pct"]')
        self.assertEqual(field.get_attribute("type"), "text")
        self.assertEqual(field.get_attribute("inputmode"), "decimal")

        self._log_a_real_week()
        self._navigate("plan")
        self.page.wait_for_function(
            "document.querySelector('#plan-form [name=\"target_bf_pct\"]').value !== ''"
        )
        self.page.fill('#plan-form [name="target_bf_pct"]', "15")
        field.fill("")
        field.press_sequentially("-0.5")
        self.assertEqual(field.input_value(), "-0.5")
        self.page.click('#plan-form button[type=submit]')
        self.page.wait_for_selector("#plan-preview-result:not([hidden])")


if __name__ == "__main__":
    unittest.main()
