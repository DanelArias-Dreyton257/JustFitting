"""Playwright browser tests for views.js's pure DOM-rendering functions.

Boots the real static JS (via harness_app.create_harness_app) in a headless
Chromium tab and drives the module's exports directly -- no mocking of the
DOM, no Node.js test runner (see README's "Phase 1.6" note).
"""

import unittest

from playwright.sync_api import sync_playwright

from client.test.browser.harness_app import create_harness_app
from client.test.browser.live_server import LiveServer


class ViewsTest(unittest.TestCase):
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
        self.page.goto(f"{self.server.url}/harness/views")
        self.page.wait_for_function("window.__viewsReady === true")

    def tearDown(self):
        self.page.close()

    def _hidden(self, selector: str) -> bool:
        return self.page.eval_on_selector(selector, "el => el.hidden")

    def test_render_alerts_lists_each_alert_and_unhides_the_container(self):
        alerts = [
            {
                "alert_id": 1,
                "severity": "warning",
                "type": "stagnation",
                "date": "2026-01-01",
                "message": "Plateau detected",
            }
        ]
        self.page.evaluate(
            "(alerts) => window.__views.renderAlerts(document.getElementById('alerts-container'), alerts)",
            alerts,
        )
        self.assertFalse(self._hidden("#alerts-container"))
        self.assertIn("Plateau detected", self.page.inner_html("#alerts-container"))

    def test_render_alerts_with_none_hides_and_clears_the_container(self):
        self.page.evaluate(
            "() => window.__views.renderAlerts(document.getElementById('alerts-container'), [])"
        )
        self.assertTrue(self._hidden("#alerts-container"))
        self.assertEqual(self.page.inner_html("#alerts-container"), "")

    def test_render_sex_disclaimer_shown_for_a_female_profile(self):
        self.page.evaluate(
            "(profile) => window.__views.renderSexDisclaimer(document.getElementById('sex-disclaimer'), profile)",
            {"sex": 0},
        )
        self.assertFalse(self._hidden("#sex-disclaimer"))
        self.assertIn("male-only", self.page.inner_text("#sex-disclaimer"))

    def test_render_sex_disclaimer_hidden_for_a_male_profile(self):
        self.page.evaluate(
            "(profile) => window.__views.renderSexDisclaimer(document.getElementById('sex-disclaimer'), profile)",
            {"sex": 1},
        )
        self.assertTrue(self._hidden("#sex-disclaimer"))

    def test_show_wizard_step_toggles_the_active_step_and_nav_buttons(self):
        self.page.evaluate(
            "() => window.__views.showWizardStep(document.getElementById('log-form'), 2, 4)"
        )
        self.assertFalse(self._hidden('.wizard-step[data-step="2"]'))
        self.assertTrue(self._hidden('.wizard-step[data-step="1"]'))
        self.assertFalse(self._hidden("#log-back"))
        self.assertFalse(self._hidden("#log-next"))
        self.assertTrue(self._hidden("#log-save"))

    def test_show_wizard_step_on_the_last_step_reveals_save_and_hides_next(self):
        self.page.evaluate(
            "() => window.__views.showWizardStep(document.getElementById('log-form'), 4, 4)"
        )
        self.assertTrue(self._hidden("#log-next"))
        self.assertFalse(self._hidden("#log-save"))

    def test_render_log_review_lists_the_given_values(self):
        self.page.evaluate(
            "(values) => window.__views.renderLogReview(document.getElementById('log-review'), values)",
            {
                "date": "2026-07-01",
                "weight_kg": 90.5,
                "waist_cm": 80,
                "neck_cm": 35,
                "intake_kcal": 2000,
                "steps": 5000,
            },
        )
        content = self.page.inner_html("#log-review")
        self.assertIn("90.5 kg", content)
        self.assertIn("5000", content)


if __name__ == "__main__":
    unittest.main()
