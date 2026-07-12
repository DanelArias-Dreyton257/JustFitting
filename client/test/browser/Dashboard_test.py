"""Playwright browser tests for the simplified dashboard-as-home summary
(Phase 4.2) -- drives the real client app (client.src.Client.create_client_app)
against a real, in-process Flask API, so this exercises the actual shipped
app.js/views.js/index.html/style.css, not a fixture.
"""

import os
import re
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


class DashboardTest(unittest.TestCase):
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
        self._register_and_log_in(f"dashtester_{self._testMethodName}")

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

    def _log_measurement(self, date: str, waist_cm: float = 80, neck_cm: float = 35):
        # Phase 9.1 (see README): waist/neck are resolved from
        # body_measurements (most recent row on or before a log's date), no
        # longer part of the Log wizard -- every Dashboard metric that
        # depends on a computed body fat/mass (MetricsSeriesService drops any
        # week it can't resolve a measurement for, entirely) needs one of
        # these logged via the real Body view first.
        #
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
        self.page.fill("#body-date-input", date)
        self.page.fill('#body-form [name="waist_cm"]', str(waist_cm))
        self.page.fill('#body-form [name="neck_cm"]', str(neck_cm))
        self.page.click("#body-save")
        self.page.wait_for_selector(f'#body-table tbody tr td:text-is("{date}")')

    def _log_week(self, date: str, weight_kg: float):
        self._log_measurement(date)
        self._navigate("log")
        # Phase 4.4: the wizard's date is derived from the Log view's
        # day/week navigator (a hidden input), not a directly-editable
        # field -- jump the navigator's date-picker there first.
        self.page.eval_on_selector(
            "#log-nav-date",
            "(el, value) => { el.value = value; el.dispatchEvent(new Event('change')); }",
            date,
        )
        self.page.fill('#log-form [name="weight_kg"]', str(weight_kg))
        self.page.click("#log-next")
        self.page.fill('#log-form [name="intake_kcal"]', "2000")
        self.page.fill('#log-form [name="steps"]', "5000")
        self.page.click("#log-next")
        self.page.click("#log-save")
        self.page.wait_for_selector(f'#log-table tbody tr td:text-is("{date}")')

    def _go_to_dashboard(self):
        self._navigate("dashboard")

    def _today_iso(self):
        # Committing a real goal (Phase 8.1/5.3) scopes the computed series
        # to dates on/after that goal's own start_date, which _set_goal
        # defaults to today -- any test that logs a week and then commits a
        # goal (without separately backdating it) needs that log dated
        # today too, or it falls outside the new goal's period and the
        # series comes back empty.
        return self.page.evaluate(
            "() => { const d = new Date(); "
            "return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-"
            "${String(d.getDate()).padStart(2, '0')}`; }"
        )

    def _set_goal(self, target_bf_pct="15", weekly_rate_pct="-0.5", direction="cut"):
        # A brand-new account's auto-assigned default goal has weekly_rate=0
        # (Phase 5.2), which Trajectory.compute_weeks_to_goal treats
        # specially (weeks_to_goal stays 0, never a positive figure) -- a
        # real, deliberately-committed goal is needed to exercise anything
        # that depends on a positive weeks_to_goal, via the same
        # preview-then-commit flow the Plan tab always uses (Phase 5.8).
        # Phase 12.3: direction now comes from the explicit selector, not
        # weekly_rate's sign -- target_bf_pct is read as "target body fat"
        # for a cut but "target lean mass" for a bulk (Phase 12.3's own
        # display convention), so a bulk caller should pass the lean-mass
        # equivalent (e.g. 85 for a 15% body fat target).
        self._navigate("plan")
        self.page.wait_for_function(
            "document.querySelector('#plan-form [name=\"target_bf_pct\"]').value !== ''"
        )
        if direction == "bulk":
            self.page.check("#plan-direction-bulk")
        self.page.fill('#plan-form [name="target_bf_pct"]', target_bf_pct)
        self.page.fill('#plan-form [name="weekly_rate_pct"]', weekly_rate_pct)
        self.page.click('#plan-form button[type=submit]')
        self.page.wait_for_selector("#plan-preview-result:not([hidden])")
        with self.page.expect_response(
            lambda r: r.url.endswith("/api/users/me") and r.request.method == "PUT"
        ):
            self.page.click("#plan-commit-btn")

    def test_summary_sections_render_without_expanding_charts(self):
        self._log_week("2026-06-01", 90.0)
        self._log_week("2026-06-08", 89.0)
        self._go_to_dashboard()

        self.page.wait_for_selector("#summary-weight-stats .stat-tile")
        # `.stat-tile .label` is rendered all-caps via CSS text-transform,
        # so compare case-insensitively rather than against the source casing.
        weight_text = self.page.inner_text("#summary-weight-stats").lower()
        self.assertIn("weight", weight_text)
        self.assertIn("body fat", weight_text)
        self.assertIn("lean mass", weight_text)
        # A second logged week should surface a change vs the previous one.
        self.assertIn("kg", self.page.inner_text("#summary-weight-stats .delta"))

        calories_text = self.page.inner_text("#summary-calories-stats").lower()
        self.assertIn("target calories", calories_text)
        self.assertIn("tdee", calories_text)

        # Phase 12.4: this account never commits a real goal (still on the
        # Phase 5.2 placeholder), so the Goal summary shows the "maintain"
        # message rather than target-body-fat/weight tiles built from a
        # value the user never chose -- see
        # test_target_weight_tile_shows_goal_weight_and_remaining_distance_delta
        # and test_goal_summary_reframes_tiles_for_a_bulk_goal below for the
        # real-goal tile content this used to assert here.
        goal_text = self.page.inner_text("#summary-goal-stats").lower()
        self.assertIn("maintain (no goal set yet)", goal_text)

    def test_chart_grid_is_collapsed_and_lazy_loaded(self):
        self._log_week("2026-06-01", 90.0)
        self._go_to_dashboard()

        self.assertIsNone(self.page.get_attribute("#dashboard-details", "open"))
        self.assertEqual(
            self.page.eval_on_selector("#chart-weight", "el => el.childElementCount"), 0
        )

        self.page.click("#dashboard-details > summary")
        self.page.wait_for_function(
            "document.getElementById('chart-weight').childElementCount > 0"
        )
        self.assertIsNotNone(self.page.get_attribute("#dashboard-details", "open"))

    def test_projection_toggle_overlays_forecast_and_marker(self):
        # Projection.project_series_with_inputs needs >= 2 real logs to fit
        # a trend, so two weeks are logged before expanding the charts.
        self._log_week("2026-06-01", 90.0)
        self._log_week("2026-06-08", 89.0)
        self._go_to_dashboard()
        self.page.click("#dashboard-details > summary")
        self.page.wait_for_function(
            "document.getElementById('chart-weight').childElementCount > 0"
        )

        def weight_points():
            return self.page.eval_on_selector_all("#chart-weight circle", "els => els.length")

        def marker_lines():
            return self.page.eval_on_selector_all(
                "#chart-weight .chart-marker-line", "els => els.length"
            )

        base_count = weight_points()
        self.assertEqual(base_count, 2)
        self.assertEqual(marker_lines(), 0)

        self.page.check("#dashboard-projection-toggle")
        self.page.wait_for_function(
            f"document.querySelectorAll('#chart-weight circle').length > {base_count}"
        )
        # Default forecast window is 4 weeks appended past the 2 real logs.
        self.assertEqual(weight_points(), base_count + 4)
        self.assertEqual(marker_lines(), 1)

        self.page.select_option("#dashboard-projection-weeks", "8")
        self.page.wait_for_function(
            f"document.querySelectorAll('#chart-weight circle').length === {base_count + 8}"
        )

        self.page.uncheck("#dashboard-projection-toggle")
        self.page.wait_for_function(
            f"document.querySelectorAll('#chart-weight circle').length === {base_count}"
        )
        self.assertEqual(marker_lines(), 0)

    def test_goal_trajectory_marker_excludes_a_future_dated_goal_change(self):
        # Every account's initial goal plan is start_date=today (real wall-
        # clock date), which -- unlike the fixed 2026-06-xx log dates used
        # throughout this suite -- can land after the last logged week. That
        # goal-change marker used to be silently clamped to the chart's
        # right edge (off the real-only date domain); once the projection
        # toggle widens the domain, it must not reappear mid-chart as a
        # second, unrelated marker alongside "Last logged".
        self._log_week("2026-06-01", 90.0)
        self._log_week("2026-06-08", 89.0)
        self._go_to_dashboard()
        self.page.click("#dashboard-details > summary")
        self.page.wait_for_function(
            "document.getElementById('chart-weight').childElementCount > 0"
        )

        self.page.check("#dashboard-projection-toggle")
        self.page.wait_for_function(
            "document.querySelectorAll('#chart-weight circle').length > 2"
        )

        marker_titles = self.page.eval_on_selector_all(
            "#chart-goal-trajectory .chart-marker-line title", "els => els.map(e => e.textContent)"
        )
        self.assertEqual(marker_titles, ["Last logged"])

    def test_goal_trajectory_marker_shows_a_real_goal_change(self):
        # The account's very first-ever goal (the Phase 5.2 placeholder)
        # never gets a "Plan changed" marker (the test above) -- but a
        # real, deliberately-committed goal change (via the Plan tab,
        # _set_goal here) is a genuine change and must still get one.
        self._log_week("2026-06-01", 90.0)
        self._log_week("2026-06-08", 89.0)
        self._set_goal()
        # _set_goal's own commit handler awaits refreshPlan() after its PUT
        # resolves, which re-fetches the goal list and only then repopulates
        # #goal-start-date-input with the new goal's real start_date (today)
        # -- wait for that settled value before touching the field, so this
        # fill() below isn't racing that in-flight refresh and getting
        # silently overwritten once it lands.
        today_iso = self.page.evaluate(
            "() => { const d = new Date(); "
            "return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-"
            "${String(d.getDate()).padStart(2, '0')}`; }"
        )
        self.page.wait_for_function(
            f"document.getElementById('goal-start-date-input').value === '{today_iso}'"
        )
        # Committing a goal (Phase 8.1/5.3) scopes computed series to dates
        # on/after its own start_date, which _set_goal defaults to today --
        # after the two fixed 2026-06-xx logs above. Backdating it (Phase
        # 8.1's own "Edit start date" control, already on the Plan tab) to
        # match them is exactly the real workflow this exists for, and
        # keeps those logs inside the new goal's active period so the
        # chart actually has real data to render.
        self.page.fill("#goal-start-date-input", "2026-06-01")
        self.page.click("#goal-start-date-form button[type=submit]")
        self.page.wait_for_function(
            "document.getElementById('goal-start-date-input').value === '2026-06-01'"
        )

        self._go_to_dashboard()
        self.page.click("#dashboard-details > summary")
        self.page.wait_for_function(
            "document.getElementById('chart-weight').childElementCount > 0"
        )

        marker_titles = self.page.eval_on_selector_all(
            "#chart-goal-trajectory .chart-marker-line title", "els => els.map(e => e.textContent)"
        )
        self.assertTrue(any(t.startswith("Plan changed") for t in marker_titles))

    def _target_weight_kg(self):
        text = self.page.locator(
            "#summary-goal-stats .stat-tile", has_text="Target weight"
        ).locator(".value").inner_text()
        return float(text.replace(" kg", "").strip())

    def _target_weight_delta_kg(self):
        text = self.page.locator(
            "#summary-goal-stats .stat-tile", has_text="Target weight"
        ).locator(".delta").inner_text()
        match = re.search(r"(-?\d+\.\d+)\s*kg to goal", text)
        return float(match.group(1))

    def _wait_for_weight_value(self, expected_prefix):
        # The Weight tile and the Weight-to-goal tile are rendered together
        # from the same fetch, so waiting for the former to reflect the new
        # weight is a reliable signal the latter has refreshed too --
        # `.stat-tile` already exists in the DOM from the previous render
        # (only its content changes), so waiting on its mere presence would
        # race the fetch and read stale content.
        self.page.wait_for_function(
            "expected => document.querySelector('#summary-weight-stats .stat-tile .value')"
            "?.innerText.trim().startsWith(expected)",
            arg=expected_prefix,
        )

    def _fetch_metrics_latest(self):
        return self.page.evaluate(
            """async () => {
                const token = localStorage.getItem('justfitting.token');
                const res = await fetch(
                    `${window.JUSTFITTING_API_BASE_URL}/api/metrics/latest`,
                    { headers: { Authorization: `Bearer ${token}` } }
                );
                return res.json();
            }"""
        )

    def test_target_weight_tile_shows_goal_weight_and_remaining_distance_delta(self):
        # Phase 5.5's bug: "Weight to goal" used to read weight_to_shed_kg
        # (this week's incremental target change), which for a steady weekly
        # rate is always roughly the same small figure regardless of how
        # close the goal actually is, rather than the actual remaining
        # distance to final_weight_kg. Phase 5.9 then flipped the tile to
        # lead with the target weight itself, with the remaining distance
        # as an arrowed subtitle -- verify both halves against the API.
        # Phase 12.4: the tile only renders once a real goal is committed
        # (the Phase 5.2 placeholder shows a "maintain" message instead),
        # so this now needs _set_goal(), with the log dated today to stay
        # inside the new goal's scoped period (see _today_iso).
        self._log_week(self._today_iso(), 95.0)
        self._set_goal()
        self._go_to_dashboard()
        self._wait_for_weight_value("95.0")
        metrics = self._fetch_metrics_latest()
        current_weight = metrics["fat_mass_kg"] + metrics["lean_mass_kg"]
        expected_target_weight = metrics["final_weight_kg"]
        expected_remaining = expected_target_weight - current_weight
        # The pre-fix figure (weight_to_shed_kg) would have been ~0.45-0.5kg
        # here regardless of proximity to goal -- assert the fix isn't that.
        self.assertNotAlmostEqual(
            abs(metrics["weight_to_shed_kg"]), abs(expected_remaining), places=1
        )
        self.assertAlmostEqual(self._target_weight_kg(), expected_target_weight, places=1)
        self.assertAlmostEqual(self._target_weight_delta_kg(), expected_remaining, places=1)

    def test_goal_summary_shows_maintain_placeholder_for_a_fresh_account(self):
        # Phase 12.4: the account's auto-assigned placeholder goal (Phase
        # 5.2, weekly_rate=0.0) is never a real, deliberately-chosen goal --
        # the Goal summary must say so plainly instead of showing a
        # target-body-fat figure built from a value the user never picked.
        self._log_week("2026-06-01", 90.0)
        self._go_to_dashboard()
        self._wait_for_weight_value("90.0")
        self.page.wait_for_selector("#summary-goal-stats")
        goal_text = self.page.inner_text("#summary-goal-stats")
        self.assertIn("Maintain (no goal set yet)", goal_text)
        self.assertNotIn("Target body fat", goal_text)

    def test_goal_summary_reframes_tiles_for_a_bulk_goal(self):
        # Phase 12.4: a bulk goal's Goal summary reframes to "Target lean
        # mass" (the complement of the stored target_bf) and "Target weight
        # (keep fat steady)" (final_weight_kg now assumes fat mass, not
        # lean mass, stays constant -- see docs/composition_spec.md's
        # "Phase 12" section). Log dated today to stay inside the new
        # goal's scoped period (see _today_iso).
        self._log_week(self._today_iso(), 90.0)
        self._set_goal(target_bf_pct="85", weekly_rate_pct="0.5", direction="bulk")
        self._go_to_dashboard()
        self.page.wait_for_selector("#summary-goal-stats .stat-tile")
        # `.stat-tile .label` renders all-caps via CSS text-transform, so
        # compare case-insensitively rather than against the source casing.
        goal_text = self.page.inner_text("#summary-goal-stats").lower()
        self.assertIn("target lean mass", goal_text)
        self.assertIn("target weight (keep fat steady)", goal_text)
        self.assertNotIn("target body fat", goal_text)
        self.assertNotIn("target weight (keep lean)", goal_text)

    def test_calories_summary_has_subtitles_and_logged_intake_tile(self):
        self._log_week("2026-06-01", 90.0)
        self._go_to_dashboard()
        self.page.wait_for_selector("#summary-calories-stats .stat-tile")
        calories_text = self.page.inner_text("#summary-calories-stats").lower()
        self.assertIn("what to eat", calories_text)
        self.assertIn("estimated calories burned", calories_text)
        self.assertIn("actual vs target/day", calories_text)
        self.assertIn("this week's intake", calories_text)
        # This week's intake tile comes before Adherence.
        self.assertLess(
            calories_text.index("this week's intake"), calories_text.index("adherence")
        )
        # _log_week logs intake_kcal=2000.
        self.assertIn("2000 kcal", calories_text)

    def test_last_logged_info_shows_the_latest_real_log_date(self):
        # Phase 11.2 (see README): a small subtitle derived client-side from
        # the max real-log date already fetched for the dashboard.
        self._log_week("2026-06-01", 90.0)
        self._log_week("2026-06-08", 89.0)
        self._go_to_dashboard()
        self.page.wait_for_function(
            "document.getElementById('summary-last-logged').innerText.trim().length > 0"
        )
        text = self.page.inner_text("#summary-last-logged")
        self.assertIn("Last logged:", text)
        self.assertIn("2026-06-08", text)

    def test_goal_progress_bar_renders_for_a_computable_account(self):
        # Phase 11.1 (see README): a full-width progress bar over
        # [goal start_date, today + weeks_to_goal], fed by GET
        # /api/users/me/goals and GET /api/metrics/latest. The default
        # auto-assigned goal (weekly_rate=0, Phase 5.2) never has a positive
        # weeks_to_goal, so a real goal has to be committed first -- and
        # since committing one (Phase 8.1/5.3) scopes the computed series to
        # dates on/after the new goal's own start_date (today), the log used
        # to compute against has to be dated today too, not a fixed past
        # date like every other test in this file uses.
        today_iso = self.page.evaluate(
            "() => { const d = new Date(); "
            "return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-"
            "${String(d.getDate()).padStart(2, '0')}`; }"
        )
        self._log_week(today_iso, 90.0)
        self._set_goal()
        self._go_to_dashboard()
        self.page.wait_for_selector("#dashboard-goal-progress .goal-progress-bar")
        progress = self.page.get_attribute(
            "#dashboard-goal-progress .goal-progress-bar", "aria-valuenow"
        )
        self.assertIsNotNone(progress)
        self.assertGreaterEqual(float(progress), 0.0)
        fill_width = self.page.eval_on_selector(
            "#dashboard-goal-progress .goal-progress-bar-fill", "el => el.style.width"
        )
        self.assertTrue(fill_width.endswith("%"))
        labels_text = self.page.inner_text("#dashboard-goal-progress .goal-progress-bar-labels")
        self.assertIn("weeks left", labels_text)

    def test_unconfigured_goal_alert_shows_for_a_fresh_account_and_is_dismissible(self):
        # Phase 5.2 follow-up: a brand-new account's auto-assigned default
        # goal (0% weekly rate) surfaces a reminder to visit the Plan tab --
        # even before any log exists, via the same alerts panel/dismiss
        # flow every other alert already uses.
        self._go_to_dashboard()
        self.page.wait_for_selector("#dashboard-alerts .alert-item")
        self.assertEqual(
            self.page.get_attribute("#dashboard-alerts .alert-item", "data-type"),
            "unconfigured_goal",
        )

        self.page.click("#dashboard-alerts .alert-dismiss-btn")
        self.page.wait_for_function(
            "document.querySelectorAll('#dashboard-alerts .alert-item').length === 0"
        )

    def test_dashboard_with_no_logs_shows_placeholders_not_errors(self):
        # A brand-new account has no logs yet -- summary sections should
        # degrade to a friendly message instead of throwing on null metrics.
        self._go_to_dashboard()
        self.page.wait_for_selector("#summary-weight-stats .disclaimer")
        self.assertIn("Log a week", self.page.inner_text("#summary-weight-stats"))
        self.assertIn("Log a week", self.page.inner_text("#summary-calories-stats"))
        self.assertIn("Log a week", self.page.inner_text("#summary-goal-stats"))
        # Phase 11.1/11.2: neither the progress bar nor the last-logged line
        # has anything to show yet -- no real log and no computable metrics.
        self.assertEqual(self.page.inner_text("#summary-last-logged").strip(), "")
        self.assertEqual(self.page.inner_text("#dashboard-goal-progress").strip(), "")

    def _set_activity_goal(self, steps_goal=None, cardio_kcal_goal=None):
        # navigate("plan") calls refreshPlan() unawaited, which fills
        # #activity-goal-form asynchronously from GET
        # /api/users/me/activity-goal (alongside the main goal's own data) --
        # the same navigate()-races-an-unawaited-refresh shape this project
        # has fixed for every other view (see README/CHANGELOG). Waiting for
        # that GET to resolve before filling anything avoids the race rather
        # than reproducing it.
        self.page.click("#nav-toggle")
        with self.page.expect_response(
            lambda r: "/api/users/me/activity-goal" in r.url and r.request.method == "GET"
        ):
            self.page.click('.nav-link[data-view="plan"]')
        self.page.wait_for_selector("#activity-goal-form")
        if steps_goal is not None:
            self.page.fill('#activity-goal-form [name="steps_goal"]', str(steps_goal))
        if cardio_kcal_goal is not None:
            self.page.fill(
                '#activity-goal-form [name="cardio_kcal_goal"]', str(cardio_kcal_goal)
            )
        with self.page.expect_response(
            lambda r: "/api/users/me/activity-goal" in r.url and r.request.method == "PUT"
        ):
            self.page.click('#activity-goal-form button[type=submit]')

    def test_today_section_shows_partial_log_estimate_and_activity_goal(self):
        # Phase 10.2 (Today dashboard section, see README): a still-partial
        # today log (steps only, via the Phase 7.4 by-date upsert route) is
        # enough to surface an estimate on the Dashboard, without waiting
        # for a full computable week.
        self._log_week("2026-06-01", 90.0)
        self._set_activity_goal(steps_goal=10000, cardio_kcal_goal=400)

        # Local date, matching both app.js's own toIsoDate() helper and the
        # server's date.today() (both run on this same machine) -- a UTC
        # ISO string can land on a different calendar day near midnight.
        today_iso = self.page.evaluate(
            "() => { const d = new Date(); "
            "return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-"
            "${String(d.getDate()).padStart(2, '0')}`; }"
        )
        self.page.evaluate(
            """async (date) => {
                const token = localStorage.getItem('justfitting.token');
                await fetch(
                    `${window.JUSTFITTING_API_BASE_URL}/api/logs/by-date/${date}`,
                    {
                        method: 'PUT',
                        headers: {
                            'Content-Type': 'application/json',
                            Authorization: `Bearer ${token}`,
                        },
                        body: JSON.stringify({ steps: 4000, cardio_kcal: 150 }),
                    }
                );
            }""",
            today_iso,
        )

        self._go_to_dashboard()
        # Content-based wait, not mere-presence (see _wait_for_weight_value's
        # own comment above): #summary-today-stats already has stat-tiles
        # from the previous dashboard visit in setUp, so waiting for a
        # .stat-tile to merely exist would race this test's own fetch and
        # read stale (pre-today-log) content.
        self.page.wait_for_function(
            "document.getElementById('summary-today-stats').innerText.toLowerCase()"
            ".includes('6000 left of 10000')"
        )
        today_text = self.page.inner_text("#summary-today-stats").lower()
        self.assertIn("steps done", today_text)
        self.assertIn("6000 left of 10000", today_text)
        self.assertIn("tef / neat / eat today", today_text)
        self.assertIn("cardio left today", today_text)
        self.assertIn("250 kcal", today_text)


if __name__ == "__main__":
    unittest.main()
