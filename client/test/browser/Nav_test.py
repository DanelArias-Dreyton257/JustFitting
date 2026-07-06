"""Playwright browser tests for the consolidated hamburger nav (Phase 4.1)
-- drives the real client app (client.src.Client.create_client_app) against a
real, in-process Flask API, so this exercises the actual shipped app.js/
index.html/style.css, not a fixture.
"""

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


class NavTest(unittest.TestCase):
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
        self._register_and_log_in(f"navtester_{self._testMethodName}")

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

    def _hidden(self, selector: str) -> bool:
        # Checks actual rendering (getComputedStyle), not just the `hidden`
        # IDL property -- a CSS rule on the element's own class can set
        # `display` and silently override the browser's default
        # `[hidden] { display: none }`, so the attribute alone can't be
        # trusted to mean "not visible".
        return not self.page.is_visible(selector)

    def test_menu_is_closed_by_default_after_login(self):
        self.assertFalse(self._hidden("#nav-toggle"))
        self.assertTrue(self._hidden("#nav"))
        self.assertEqual(self.page.get_attribute("#nav-toggle", "aria-expanded"), "false")

    def test_clicking_the_toggle_opens_the_menu(self):
        self.page.click("#nav-toggle")
        self.assertFalse(self._hidden("#nav"))
        self.assertEqual(self.page.get_attribute("#nav-toggle", "aria-expanded"), "true")

    def test_clicking_a_menu_item_navigates_closes_the_menu_and_marks_it_active(self):
        self.page.click("#nav-toggle")
        self.page.click('.nav-link[data-view="settings"]')
        self.assertTrue(self._hidden("#nav"))
        self.assertFalse(self._hidden("#view-settings"))
        self.assertTrue(self._hidden("#view-dashboard"))
        self.assertTrue(
            self.page.eval_on_selector(
                '.nav-link[data-view="settings"]', "el => el.classList.contains('active')"
            )
        )

    def test_escape_closes_the_menu_and_returns_focus_to_the_toggle(self):
        self.page.click("#nav-toggle")
        self.page.keyboard.press("Escape")
        self.assertTrue(self._hidden("#nav"))
        self.assertTrue(
            self.page.eval_on_selector("#nav-toggle", "el => el === document.activeElement")
        )

    def test_clicking_outside_the_menu_closes_it(self):
        self.page.click("#nav-toggle")
        self.page.click(".brand")
        self.assertTrue(self._hidden("#nav"))

    def test_logging_out_hides_the_toggle_and_closes_the_menu(self):
        self.page.click("#nav-toggle")
        self.page.click("#logout-btn")
        self.page.wait_for_selector("#view-auth:not([hidden])")
        self.assertTrue(self._hidden("#nav-toggle"))
        self.assertTrue(self._hidden("#nav"))


if __name__ == "__main__":
    unittest.main()
