"""Playwright browser tests for api.js -- drives its exported functions from
inside a real headless-Chromium tab against a real, in-process Flask API
(server.src.api.app.create_app), so this is an actual network round-trip
through the browser's fetch(), not a mocked request.
"""

import shutil
import tempfile
import unittest
from pathlib import Path

from playwright.sync_api import sync_playwright

from client.test.browser.harness_app import create_harness_app
from client.test.browser.live_server import LiveServer
from server.src.api.app import create_app


class ApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db_dir = tempfile.mkdtemp(prefix="justfitting-browser-test-")
        cls.db_path = str(Path(cls.db_dir) / "browser_test.db")

        api_app = create_app({"DB_PATH": cls.db_path, "CORS_ORIGINS": "*"})
        cls.api_server = LiveServer(api_app)
        cls.api_server.start()

        cls.client_server = LiveServer(create_harness_app(api_base_url=cls.api_server.url))
        cls.client_server.start()

        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        cls.client_server.stop()
        cls.api_server.stop()
        shutil.rmtree(cls.db_dir, ignore_errors=True)

    def setUp(self):
        self.page = self.browser.new_page()
        self.page.goto(f"{self.client_server.url}/harness/api")
        self.page.wait_for_function("window.__apiReady === true")

    def tearDown(self):
        self.page.close()

    def test_register_and_login_round_trip_through_a_real_browser_fetch(self):
        payload = {
            "username": "browsertest",
            "email": "browsertest@example.com",
            "password": "s3cret123",
            "height_cm": 176,
            "sex": 1,
            "birthdate": "2001-08-22",
            "target_bf": 0.15,
            "weekly_rate": -0.005,
        }
        registered = self.page.evaluate(
            "(payload) => window.__api.register(payload)", payload
        )
        self.assertIn("token", registered)
        self.assertEqual(registered["profile"]["height_cm"], 176)

        logged_in = self.page.evaluate(
            "(creds) => window.__api.login(creds)",
            {"username": "browsertest", "password": "s3cret123"},
        )
        self.assertIn("token", logged_in)

    def test_unauthenticated_me_call_raises_an_api_error_with_401(self):
        error = self.page.evaluate(
            """
            async () => {
              try {
                await window.__api.me();
                return null;
              } catch (err) {
                return { status: err.status, message: err.message };
              }
            }
            """
        )
        self.assertIsNotNone(error)
        self.assertEqual(error["status"], 401)


if __name__ == "__main__":
    unittest.main()
