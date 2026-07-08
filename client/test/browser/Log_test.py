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

    def _navigate(self, view: str):
        self.page.click("#nav-toggle")
        self.page.click(f'.nav-link[data-view="{view}"]')
        self.page.wait_for_selector(f"#view-{view}:not([hidden])")

    def _navigate_to_log(self):
        self._navigate("log")

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

    def _set_show_projected(self, checked: bool):
        # Phase 4.5: the preference lives in Settings (a localStorage-backed
        # browser preference, not part of the historized account settings
        # form), not on the Log view itself.
        self._navigate("settings")
        if checked:
            self.page.check("#settings-show-projected-logs")
        else:
            self.page.uncheck("#settings-show-projected-logs")
        self._navigate_to_log()

    def test_show_projected_preference_injects_a_projected_row_past_the_last_logged_week(self):
        # Projection.project_series_with_inputs needs >= 2 real logs to fit a
        # trend (same precondition Dashboard_test.py's own projection test
        # relies on).
        iso_week1 = _MONDAY.isoformat()
        iso_week2 = (_MONDAY + datetime.timedelta(days=7)).isoformat()
        iso_future = (_MONDAY + datetime.timedelta(days=14)).isoformat()
        self._log_on(iso_week1, 90.0)
        self._log_on(iso_week2, 89.0)

        self._set_show_projected(True)
        self._jump_to_date(iso_future)
        self.page.wait_for_selector(f'#log-table tbody tr td:text-is("{iso_future}")')
        self.assertTrue(self.page.is_visible("#log-table"))
        self.assertFalse(self.page.is_visible("#log-list-empty"))

        row = self.page.locator("#log-table tbody tr").first
        row_text = row.inner_text().lower()
        self.assertIn("projected", row_text)
        self.assertIn("weekly", row_text)
        self.assertEqual(row.locator(".delete-log-btn").count(), 0)
        # Weight is the row's 2nd cell (Date is 1st) -- rounded to 1 decimal.
        weight_cell = row.locator("td").nth(1).inner_text()
        self.assertRegex(weight_cell, r"^\d+\.\d$")

        self._set_show_projected(False)
        self.page.wait_for_selector("#log-list-empty:visible")
        self.assertFalse(self.page.is_visible("#log-table"))

    def test_show_projected_defaults_to_on_for_a_fresh_browser_profile(self):
        # No visit to Settings at all -- getShowProjectedLogs() treats an
        # unset localStorage key as true, so a brand-new browser profile
        # sees projected rows without having to find the checkbox first.
        iso_week1 = _MONDAY.isoformat()
        iso_week2 = (_MONDAY + datetime.timedelta(days=7)).isoformat()
        iso_future = (_MONDAY + datetime.timedelta(days=14)).isoformat()
        self._log_on(iso_week1, 90.0)
        self._log_on(iso_week2, 89.0)

        self._jump_to_date(iso_future)
        self.page.wait_for_selector(f'#log-table tbody tr td:text-is("{iso_future}")')
        self.assertIn("projected", self.page.inner_text("#log-table tbody tr").lower())

    def test_wizard_prefills_perimeters_from_last_real_log(self):
        # A brand-new account's first-ever wizard opens blank.
        self.assertEqual(
            self.page.eval_on_selector('#log-form [name="waist_cm"]', "el => el.value"), ""
        )
        self.assertEqual(
            self.page.eval_on_selector('#log-form [name="neck_cm"]', "el => el.value"), ""
        )

        self._log_on(_MONDAY.isoformat(), 90.0)

        # Right after saving, the wizard resets then re-prefills from the
        # log just saved -- proving the prefill (not leftover form state,
        # since the form is reset() before refreshLogs() re-fills it).
        self.assertEqual(
            self.page.eval_on_selector('#log-form [name="waist_cm"]', "el => el.value"), "80"
        )
        self.assertEqual(
            self.page.eval_on_selector('#log-form [name="neck_cm"]', "el => el.value"), "35"
        )

        # Still prefilled after a later "fresh wizard" reset point (a
        # day/week toggle), not just the moment right after saving.
        self.page.click("#log-nav-week")
        self.page.wait_for_function(
            "document.getElementById('log-nav-week').classList.contains('active')"
        )
        self.assertEqual(
            self.page.eval_on_selector('#log-form [name="waist_cm"]', "el => el.value"), "80"
        )
        self.assertEqual(
            self.page.eval_on_selector('#log-form [name="neck_cm"]', "el => el.value"), "35"
        )

    def test_editing_a_log_updates_the_row_in_place_and_persists_after_reload(self):
        iso_date = _MONDAY.isoformat()
        self._log_on(iso_date, 90.0)

        row = self.page.locator("#log-table tbody tr").first
        original_log_id = row.get_attribute("data-log-id")

        row.locator(".edit-log-btn").click()
        self.page.wait_for_function(
            "document.getElementById('log-save').textContent === 'Save changes'"
        )
        self.assertIn("Editing log for", self.page.inner_text("#log-form"))
        self.assertEqual(
            self.page.eval_on_selector('#log-form [name="weight_kg"]', "el => el.value"), "90"
        )
        self.assertTrue(
            self.page.eval_on_selector(
                "#log-wizard-granularity", "el => el.disabled"
            )
        )

        self.page.fill('#log-form [name="weight_kg"]', "88.5")
        self.page.click("#log-next")
        self.page.click("#log-next")
        self.page.click("#log-next")
        self.page.click("#log-save")
        self.page.wait_for_function(
            "document.querySelector('#log-table tbody tr td:nth-child(2)')?.textContent === '88.5'"
        )

        # Same row updated in place -- no new row, log_id unchanged, and the
        # wizard reverts to create-mode.
        rows = self.page.locator("#log-table tbody tr")
        self.assertEqual(rows.count(), 1)
        self.assertEqual(rows.first.get_attribute("data-log-id"), original_log_id)
        self.assertEqual(self.page.inner_text("#log-save"), "Save log")
        self.assertTrue(self.page.is_hidden("#log-cancel-edit"))
        self.assertFalse(
            self.page.eval_on_selector("#log-wizard-granularity", "el => el.disabled")
        )

        # Round-trips through a page reload (not just left in local state).
        self.page.reload()
        self._navigate_to_log()
        self._jump_to_date(iso_date)
        self.page.wait_for_selector(f'#log-table tbody tr td:text-is("{iso_date}")')
        self.assertEqual(
            self.page.locator("#log-table tbody tr").first.locator("td").nth(1).inner_text(),
            "88.5",
        )

    def test_cancel_edit_discards_changes_and_returns_to_create_mode(self):
        iso_date = _MONDAY.isoformat()
        self._log_on(iso_date, 90.0)
        original_weight = (
            self.page.locator("#log-table tbody tr").first.locator("td").nth(1).inner_text()
        )

        self.page.locator("#log-table tbody tr").first.locator(".edit-log-btn").click()
        self.page.wait_for_function(
            "document.getElementById('log-save').textContent === 'Save changes'"
        )
        self.page.fill('#log-form [name="weight_kg"]', "50")

        self.page.click("#log-cancel-edit")
        self.page.wait_for_function(
            "document.getElementById('log-save').textContent === 'Save log'"
        )
        self.assertTrue(self.page.is_hidden("#log-cancel-edit"))
        self.assertEqual(
            self.page.eval_on_selector('#log-form [name="weight_kg"]', "el => el.value"), ""
        )

        # The cancelled edit was never submitted -- the row is untouched.
        self.assertEqual(
            self.page.locator("#log-table tbody tr").first.locator("td").nth(1).inner_text(),
            original_weight,
        )

    def test_show_projected_preference_stays_inert_on_a_real_logged_day(self):
        iso_week1 = _MONDAY.isoformat()
        iso_week2 = (_MONDAY + datetime.timedelta(days=7)).isoformat()
        self._log_on(iso_week1, 90.0)
        self._log_on(iso_week2, 89.0)

        self._set_show_projected(True)
        self._jump_to_date(iso_week1)
        self.page.wait_for_function(
            "document.querySelectorAll('#log-table tbody tr').length === 1"
        )
        row = self.page.locator("#log-table tbody tr").first
        self.assertIn("real", row.inner_text().lower())
        self.assertEqual(row.locator(".delete-log-btn").count(), 1)


if __name__ == "__main__":
    unittest.main()
