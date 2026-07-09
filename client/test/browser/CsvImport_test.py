"""Playwright browser tests for csvImport.js's parseCsvLogs (Phase 7.2,
README) -- boots the real static JS in a headless Chromium tab and drives
the module's export directly, same pattern as Views_test.py.
"""

import unittest

from playwright.sync_api import sync_playwright

from client.test.browser.harness_app import create_harness_app
from client.test.browser.live_server import LiveServer


class CsvImportTest(unittest.TestCase):
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
        self.page.goto(f"{self.server.url}/harness/csv")
        self.page.wait_for_function("window.__csvImportReady === true")

    def tearDown(self):
        self.page.close()

    def _parse(self, text):
        return self.page.evaluate(
            "(text) => window.__csvImport.parseCsvLogs(text)", text
        )

    def _parse_error(self, text):
        return self.page.evaluate(
            """(text) => {
                try {
                    window.__csvImport.parseCsvLogs(text);
                    return null;
                } catch (err) {
                    return err.message;
                }
            }""",
            text,
        )

    def test_parses_required_columns_as_numbers_not_strings(self):
        text = (
            "date,weight_kg,waist_cm,neck_cm,intake_kcal,steps\n"
            "2026-01-05,91.4,89.0,37.5,2300,6200\n"
        )
        result = self._parse(text)
        self.assertEqual(
            result,
            {
                "logs": [
                    {
                        "date": "2026-01-05",
                        "weight_kg": 91.4,
                        "waist_cm": 89.0,
                        "neck_cm": 37.5,
                        "intake_kcal": 2300,
                        "steps": 6200,
                    }
                ]
            },
        )

    def test_optional_blank_columns_are_omitted_not_sent_as_empty_strings(self):
        text = (
            "date,weight_kg,waist_cm,neck_cm,intake_kcal,steps,carbs_g,fat_g,protein_g\n"
            "2026-01-05,91.4,89.0,37.5,2300,6200,,,\n"
        )
        result = self._parse(text)
        row = result["logs"][0]
        self.assertNotIn("carbs_g", row)
        self.assertNotIn("fat_g", row)
        self.assertNotIn("protein_g", row)

    def test_intake_is_real_parses_common_boolean_spellings(self):
        text = (
            "date,weight_kg,waist_cm,neck_cm,intake_kcal,steps,intake_is_real\n"
            "2026-01-05,91.4,89.0,37.5,2300,6200,false\n"
            "2026-01-06,91.0,89.0,37.5,2300,6200,TRUE\n"
        )
        result = self._parse(text)
        self.assertEqual(result["logs"][0]["intake_is_real"], False)
        self.assertEqual(result["logs"][1]["intake_is_real"], True)

    def test_blank_intake_is_real_is_omitted_rather_than_defaulting_falsy(self):
        # Guards against Python's bool("") / bool("false") gotchas if this
        # field were ever left as a raw string for the server to coerce --
        # the parser must resolve it to a real boolean or omit it entirely.
        text = (
            "date,weight_kg,waist_cm,neck_cm,intake_kcal,steps,intake_is_real\n"
            "2026-01-05,91.4,89.0,37.5,2300,6200,\n"
        )
        result = self._parse(text)
        self.assertNotIn("intake_is_real", result["logs"][0])

    def test_granularity_and_unknown_columns_pass_through_as_strings(self):
        text = (
            "date,weight_kg,waist_cm,neck_cm,intake_kcal,steps,granularity,source\n"
            "2026-01-05,91.4,89.0,37.5,2300,6200,daily,projected\n"
        )
        row = self._parse(text)["logs"][0]
        self.assertEqual(row["granularity"], "daily")
        # Present in the parsed row, but the import route ignores/forces it
        # server-side regardless (Phase 7.1) -- the parser's job is just to
        # not lose or mangle it.
        self.assertEqual(row["source"], "projected")

    def test_quoted_fields_with_embedded_commas_are_handled(self):
        text = (
            'date,weight_kg,waist_cm,neck_cm,intake_kcal,steps,granularity\n'
            '2026-01-05,91.4,89.0,37.5,2300,6200,"daily"\n'
        )
        row = self._parse(text)["logs"][0]
        self.assertEqual(row["granularity"], "daily")

    def test_blank_lines_are_ignored(self):
        text = (
            "date,weight_kg,waist_cm,neck_cm,intake_kcal,steps\n"
            "\n"
            "2026-01-05,91.4,89.0,37.5,2300,6200\n"
            "\n"
        )
        result = self._parse(text)
        self.assertEqual(len(result["logs"]), 1)

    def test_missing_required_column_raises_a_descriptive_error(self):
        text = "date,waist_cm,neck_cm,intake_kcal,steps\n2026-01-05,89.0,37.5,2300,6200\n"
        message = self._parse_error(text)
        self.assertIn("weight_kg", message)

    def test_header_only_file_produces_no_rows(self):
        text = "date,weight_kg,waist_cm,neck_cm,intake_kcal,steps\n"
        result = self._parse(text)
        self.assertEqual(result, {"logs": []})


if __name__ == "__main__":
    unittest.main()
