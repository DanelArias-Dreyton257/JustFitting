"""Playwright browser tests for the Log view's day/week navigator
(Phase 4.4) -- drives the real client app (client.src.Client.create_client_app)
against a real, in-process Flask API, same harness as Dashboard_test.py, so
this exercises the actual shipped app.js/views.js/index.html/style.css.
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
        "target_bf_pct": "15",
        "weekly_rate_pct": "-0.5",
    }


# A Monday computed from a fixed seed date -- robust regardless of which day
# of the week this suite actually runs on -- plus a couple of days inside the
# same ISO (Monday-Sunday) week, for the week-view grouping test.
_MONDAY = datetime.date(2026, 3, 1) - datetime.timedelta(
    days=datetime.date(2026, 3, 1).weekday()
)
_THURSDAY = _MONDAY + datetime.timedelta(days=3)
_TUESDAY = _MONDAY + datetime.timedelta(days=1)


class LogNavTest(unittest.TestCase):
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
        self._register_and_log_in(f"logtester_{self._testMethodName}")

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
        self._navigate_to_log()

    def _navigate_to_log(self):
        self.page.click("#nav-toggle")
        self.page.click('.nav-link[data-view="log"]')
        self.page.wait_for_selector("#view-log:not([hidden])")

    def _jump_to_date(self, iso_date: str):
        self.page.eval_on_selector(
            "#log-nav-date",
            "(el, value) => { el.value = value; el.dispatchEvent(new Event('change')); }",
            iso_date,
        )

    def _log_on(self, iso_date: str, weight_kg: float):
        self._jump_to_date(iso_date)
        self.page.fill('#log-form [name="weight_kg"]', str(weight_kg))
        self.page.click("#log-next")
        self.page.fill('#log-form [name="waist_cm"]', "80")
        self.page.fill('#log-form [name="neck_cm"]', "35")
        self.page.click("#log-next")
        self.page.fill('#log-form [name="intake_kcal"]', "2000")
        self.page.fill('#log-form [name="steps"]', "5000")
        self.page.click("#log-next")
        self.page.click("#log-save")
        self.page.wait_for_selector(f'#log-table tbody tr td:text-is("{iso_date}")')

    def test_default_is_todays_day_view_with_empty_placeholder(self):
        self.assertEqual(self.page.inner_text("#log-list-heading"), "Today's logs")
        self.assertTrue(self.page.is_visible("#log-list-empty"))
        self.assertFalse(self.page.is_visible("#log-table"))
        self.assertIn("active", self.page.get_attribute("#log-nav-day", "class"))

    def test_saving_a_log_lands_in_the_selected_day(self):
        iso_date = _MONDAY.isoformat()
        self._log_on(iso_date, 90.0)

        # Not today (a fixed 2026 date), so the heading switches from the
        # "Today's logs" default to the "Logs for <day>" form -- the exact
        # locale-formatted day string isn't asserted here, just that it
        # switched away from the default.
        self.assertEqual(self.page.inner_text("#log-list-heading")[:9], "Logs for ")
        rows = self.page.locator("#log-table tbody tr")
        self.assertEqual(rows.count(), 1)
        self.assertEqual(rows.first.locator("td").first.inner_text(), iso_date)
        self.assertFalse(self.page.is_visible("#log-list-empty"))

    def test_arrows_navigate_by_one_day(self):
        iso_monday = _MONDAY.isoformat()
        iso_tuesday = _TUESDAY.isoformat()
        self._log_on(iso_monday, 90.0)

        self.page.click("#log-nav-next")
        self.page.wait_for_function("document.getElementById('log-nav-date').value !== ''")
        self.assertEqual(self.page.eval_on_selector("#log-nav-date", "el => el.value"), iso_tuesday)
        self.assertTrue(self.page.is_visible("#log-list-empty"))
        self.assertEqual(self.page.locator("#log-table tbody tr").count(), 0)

        self.page.click("#log-nav-prev")
        self.page.wait_for_selector(f'#log-table tbody tr td:text-is("{iso_monday}")')
        self.assertEqual(self.page.locator("#log-table tbody tr").count(), 1)

    def test_week_view_groups_logs_from_the_same_iso_week_day_view_does_not(self):
        iso_monday = _MONDAY.isoformat()
        iso_thursday = _THURSDAY.isoformat()
        self._log_on(iso_monday, 90.0)
        self._log_on(iso_thursday, 89.5)

        # Day view (Thursday, the last day logged) shows only that one log.
        self.assertEqual(self.page.locator("#log-table tbody tr").count(), 1)

        self.page.click("#log-nav-week")
        self.page.wait_for_function(
            "document.querySelectorAll('#log-table tbody tr').length === 2"
        )
        self.assertIn("active", self.page.get_attribute("#log-nav-week", "class"))

        self.page.click("#log-nav-day")
        self.page.wait_for_function(
            "document.querySelectorAll('#log-table tbody tr').length === 1"
        )


if __name__ == "__main__":
    unittest.main()
