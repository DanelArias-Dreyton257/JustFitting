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
            "() => window.__views.showWizardStep(document.getElementById('log-form'), 2, 3)"
        )
        self.assertFalse(self._hidden('.wizard-step[data-step="2"]'))
        self.assertTrue(self._hidden('.wizard-step[data-step="1"]'))
        self.assertFalse(self._hidden("#log-back"))
        self.assertFalse(self._hidden("#log-next"))
        self.assertTrue(self._hidden("#log-save"))

    def test_show_wizard_step_on_the_last_step_reveals_save_and_hides_next(self):
        self.page.evaluate(
            "() => window.__views.showWizardStep(document.getElementById('log-form'), 3, 3)"
        )
        self.assertTrue(self._hidden("#log-next"))
        self.assertFalse(self._hidden("#log-save"))

    def test_render_log_table_shows_dashes_for_a_partial_row(self):
        """Phase 7.4 (partial logs, see README): a synced, steps-only row
        has no weight/macros yet -- the table shows a dash, not the
        literal string "null"."""
        logs = [
            {
                "log_id": 1,
                "date": "2026-01-05",
                "weight_kg": None,
                "intake_kcal": 2200,
                "steps": 7000,
                "cardio_kcal": 0,
                "carbs_g": None,
                "fat_g": None,
                "protein_g": None,
                "source": "real",
                "granularity": "daily",
            }
        ]
        self.page.evaluate(
            "(logs) => window.__views.renderLogTable(document.getElementById('log-table-body'), logs)",
            logs,
        )
        cells = self.page.eval_on_selector_all(
            "#log-table-body tr td", "els => els.map(el => el.textContent)"
        )
        self.assertEqual(cells[1], "—")  # weight
        self.assertEqual(cells[5], "—")  # macros (carbs/fat/protein all null)
        self.assertNotIn("null", "".join(cells))

    def test_render_log_review_lists_the_given_values(self):
        self.page.evaluate(
            "(values) => window.__views.renderLogReview(document.getElementById('log-review'), values)",
            {
                "date": "2026-07-01",
                "weight_kg": 90.5,
                "intake_kcal": 2000,
                "steps": 5000,
            },
        )
        content = self.page.inner_html("#log-review")
        self.assertIn("90.5 kg", content)
        self.assertIn("5000", content)

    def test_render_body_measurement_table_carries_forward_unset_fields(self):
        # Phase 9.3: a Quick (waist/neck-only) entry shouldn't make Chest/
        # Hips/etc. appear to reset to blank -- each field independently
        # carries forward its own most recent non-null value.
        measurements = [
            {
                "measurement_id": 1,
                "date": "2026-01-01",
                "waist_cm": 90,
                "neck_cm": 38,
                "shoulder_cm": 45,
                "chest_cm": None,
                "hips_cm": None,
                "biceps_r_cm": None,
                "biceps_l_cm": None,
                "thigh_r_cm": None,
                "thigh_l_cm": None,
                "calf_r_cm": None,
                "calf_l_cm": None,
            },
            {
                "measurement_id": 2,
                "date": "2026-01-08",
                "waist_cm": 89,
                "neck_cm": 38,
                "shoulder_cm": None,
                "chest_cm": None,
                "hips_cm": None,
                "biceps_r_cm": None,
                "biceps_l_cm": None,
                "thigh_r_cm": None,
                "thigh_l_cm": None,
                "calf_r_cm": None,
                "calf_l_cm": None,
            },
        ]
        self.page.evaluate(
            "(measurements) => window.__views.renderBodyMeasurementTable("
            "document.getElementById('body-table-body'), measurements)",
            measurements,
        )
        rows = self.page.locator("#body-table-body tr")
        self.assertEqual(rows.count(), 2)
        second_row_cells = rows.nth(1).locator("td").all_inner_texts()
        # Date, waist, neck, shoulder, ... -- shoulder (index 3) carries
        # forward the 45 from the first (Full) entry, not a dash.
        self.assertEqual(second_row_cells[0], "2026-01-08")
        self.assertEqual(second_row_cells[1], "89")
        self.assertEqual(second_row_cells[3], "45")

    def test_fill_body_measurement_form_populates_named_fields(self):
        measurement = {
            "date": "2026-02-01",
            "waist_cm": 91.5,
            "neck_cm": 39,
            "shoulder_cm": None,
            "chest_cm": None,
            "hips_cm": None,
            "biceps_r_cm": None,
            "biceps_l_cm": None,
            "thigh_r_cm": None,
            "thigh_l_cm": None,
            "calf_r_cm": None,
            "calf_l_cm": None,
        }
        self.page.evaluate(
            "(measurement) => window.__views.fillBodyMeasurementForm("
            "document.getElementById('body-form'), measurement)",
            measurement,
        )
        self.assertEqual(
            self.page.eval_on_selector('#body-form [name="date"]', "el => el.value"),
            "2026-02-01",
        )
        self.assertEqual(
            self.page.eval_on_selector('#body-form [name="waist_cm"]', "el => el.value"), "91.5"
        )
        self.assertEqual(
            self.page.eval_on_selector('#body-form [name="chest_cm"]', "el => el.value"), ""
        )


if __name__ == "__main__":
    unittest.main()
