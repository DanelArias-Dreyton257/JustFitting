"""Playwright browser tests for healthSync.js's rounding of Health Connect
readings -- a reported bug where steps/calories/macros synced from Health
Connect showed many meaningless decimal places (a sum-of-floats artifact,
e.g. carbs_g: 210.00000000000003), when 1 decimal is all that's meaningful
and all that should ever be stored. Boots the real static JS in a headless
Chromium tab, mocks the native Capacitor plugin, and drives the module's
export directly, same pattern as CsvImport_test.py.
"""

import unittest

from playwright.sync_api import sync_playwright

from client.test.browser.harness_app import create_harness_app
from client.test.browser.live_server import LiveServer


class HealthSyncTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = LiveServer(create_harness_app())
        cls.server.start()
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        cls.server.stop()

    def setUp(self):
        self.page = self.browser.new_page()
        self.page.goto(f"{self.server.url}/harness/health-sync")
        self.page.wait_for_function("window.__healthSyncReady === true")

    def tearDown(self):
        self.page.close()

    def _mock_plugin(self, readings):
        self.page.evaluate(
            """(readings) => {
                window.Capacitor = {
                    Plugins: {
                        HealthSync: {
                            readRecentReadings: async () => ({ readings }),
                        },
                    },
                };
            }""",
            readings,
        )

    def _sync(self, since_date="2026-06-01"):
        return self.page.evaluate(
            "(sinceDate) => window.__healthSync.syncRecentReadings(sinceDate)",
            since_date,
        )

    def test_steps_calories_and_macros_round_to_one_decimal(self):
        self._mock_plugin(
            [
                {
                    "date": "2026-07-01",
                    "steps": 6543.0000000000009,
                    "intake_kcal": 2199.9999999999995,
                    "carbs_g": 210.00000000000003,
                    "fat_g": 69.95000000000002,
                    "protein_g": 160.05000000000001,
                }
            ]
        )
        reading = self._sync()["readings"][0]
        self.assertEqual(reading["steps"], 6543.0)
        self.assertEqual(reading["intake_kcal"], 2200.0)
        self.assertEqual(reading["carbs_g"], 210.0)
        self.assertEqual(reading["fat_g"], 70.0)
        self.assertEqual(reading["protein_g"], 160.1)

    def test_fields_the_reading_never_had_stay_absent_not_rounded_to_null(self):
        self._mock_plugin([{"date": "2026-07-01", "steps": 5000.3333}])
        reading = self._sync()["readings"][0]
        self.assertEqual(reading["steps"], 5000.3)
        self.assertNotIn("intake_kcal", reading)
        self.assertNotIn("carbs_g", reading)
        self.assertNotIn("fat_g", reading)
        self.assertNotIn("protein_g", reading)

    def test_no_native_plugin_returns_empty_readings(self):
        self.assertEqual(self._sync(), {"readings": []})


if __name__ == "__main__":
    unittest.main()
