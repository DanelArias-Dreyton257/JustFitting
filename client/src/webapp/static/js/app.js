// Controller: holds all app state, wires DOM events to api.js and views.js.
import { api } from "./api.js";
import { parseCsvLogs } from "./csvImport.js";
import * as healthSync from "./healthSync.js";
import {
  getToken,
  setToken,
  clearToken,
  isAuthenticated,
  getShowProjectedLogs,
  setShowProjectedLogs,
} from "./session.js";
import {
  showView,
  setFormError,
  renderDashboardStats,
  renderWeightSummary,
  renderCaloriesSummary,
  renderGoalSummary,
  renderAlerts,
  renderAlertHistory,
  renderGoalHistory,
  renderLogTable,
  fillProfileForm,
  showWizardStep,
  renderLogReview,
  renderPlanStats,
  renderReport,
  renderSexDisclaimer,
  fillSettingsForm,
  renderSettingsStatus,
  renderSettingsHistory,
  renderImportSummary,
  renderHealthSyncStatus,
} from "./views.js";
import {
  drawLineChart,
  drawStackedBars,
  drawMultiLineChart,
  drawDivergingBars,
  drawMacroSplitBars,
} from "./charts.js";

const MACRO_COLORS = { protein: "#5eb3ff", fat: "#f0b94d", carbs: "#7ee787" };

// Phase 4.4: local-date (not UTC) helpers for the Log view's day/week
// navigator -- ISO week bounds mirror LogResampler.resample_to_weekly's
// own Monday-Sunday grouping convention server-side.
function toIsoDate(date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function todayIso() {
  return toIsoDate(new Date());
}

function addDays(isoDate, days) {
  const [y, m, d] = isoDate.split("-").map(Number);
  const date = new Date(y, m - 1, d);
  date.setDate(date.getDate() + days);
  return toIsoDate(date);
}

function isoWeekRange(isoDate) {
  const [y, m, d] = isoDate.split("-").map(Number);
  const date = new Date(y, m - 1, d);
  const dayOfWeek = date.getDay(); // 0 = Sun .. 6 = Sat
  const diffToMonday = dayOfWeek === 0 ? -6 : 1 - dayOfWeek;
  const monday = new Date(date);
  monday.setDate(date.getDate() + diffToMonday);
  const sunday = new Date(monday);
  sunday.setDate(monday.getDate() + 6);
  return { start: toIsoDate(monday), end: toIsoDate(sunday) };
}

function formatShortDate(isoDate) {
  const [y, m, d] = isoDate.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function formatDayLabel(isoDate) {
  const [y, m, d] = isoDate.split("-").map(Number);
  const weekday = new Date(y, m - 1, d).toLocaleDateString(undefined, {
    weekday: "long",
    month: "short",
    day: "numeric",
  });
  return isoDate === todayIso() ? `Today — ${weekday}` : weekday;
}

function formatWeekLabel(isoDate) {
  const { start, end } = isoWeekRange(isoDate);
  return `Week of ${formatShortDate(start)} – ${formatShortDate(end)}`;
}

const state = {
  profile: null,
  logs: [],
  series: [],
  gainQuality: [],
  latestMetrics: null,
  planPreviewParams: null,
  dashboardChartsLoaded: false,
  dashboardData: null,
  showProjection: false,
  projectionWeeks: 4,
  projectionCache: {},
  logNav: { selectedDate: todayIso(), viewMode: "day" },
  editingLogId: null,
};

const LOG_WIZARD_STEPS = 4;
let logWizardStep = 1;

const navButtons = document.querySelectorAll(".nav-link");
const logoutBtn = document.getElementById("logout-btn");
const navToggle = document.getElementById("nav-toggle");
const navMenu = document.getElementById("nav");

function closeNavMenu() {
  navMenu.hidden = true;
  navToggle.setAttribute("aria-expanded", "false");
}

function openNavMenu() {
  navMenu.hidden = false;
  navToggle.setAttribute("aria-expanded", "true");
}

navToggle.addEventListener("click", () => {
  if (navMenu.hidden) openNavMenu();
  else closeNavMenu();
});

document.addEventListener("click", (event) => {
  if (navMenu.hidden) return;
  if (navMenu.contains(event.target) || navToggle.contains(event.target)) return;
  closeNavMenu();
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !navMenu.hidden) {
    closeNavMenu();
    navToggle.focus();
  }
});

async function boot() {
  if (isAuthenticated()) {
    try {
      state.profile = await api.me();
      await enterApp();
      return;
    } catch (err) {
      clearToken();
    }
  }
  showAuthOnly();
}

function showAuthOnly() {
  navButtons.forEach((btn) => (btn.hidden = true));
  logoutBtn.hidden = true;
  navToggle.hidden = true;
  closeNavMenu();
  showView("auth");
}

async function enterApp() {
  navButtons.forEach((btn) => (btn.hidden = false));
  logoutBtn.hidden = false;
  navToggle.hidden = false;
  state.dashboardChartsLoaded = false;
  state.dashboardData = null;
  state.showProjection = false;
  state.projectionWeeks = 4;
  state.projectionCache = {};
  state.logNav = { selectedDate: todayIso(), viewMode: "day" };
  state.editingLogId = null;
  const dashboardDetails = document.getElementById("dashboard-details");
  if (dashboardDetails) dashboardDetails.open = false;
  const projectionToggle = document.getElementById("dashboard-projection-toggle");
  if (projectionToggle) projectionToggle.checked = false;
  const projectionWeeksSelect = document.getElementById("dashboard-projection-weeks");
  if (projectionWeeksSelect) projectionWeeksSelect.value = "4";
  navigate("dashboard");
}

function navigate(viewName) {
  closeNavMenu();
  showView(viewName);
  if (viewName === "dashboard") refreshDashboardSummary();
  if (viewName === "log") {
    // Render the nav label/heading and the (possibly still-empty) filtered
    // list synchronously from already-known state -- state.logNav always
    // defaults to today/day-view and state.logs starts as [] -- so the view
    // never shows a raw-HTML-default flash while the async refreshLogs()
    // fetch is in flight.
    renderLogNav();
    renderFilteredLogList();
    refreshLogs();
  }
  if (viewName === "plan") refreshPlan();
  if (viewName === "account") {
    // Render synchronously from already-known state -- state.profile is
    // always populated by boot() before any navigation is possible, so
    // there's no "still loading" gap to fill. This used to call the
    // async refreshAccount(), which re-fetched GET /api/users/me
    // unawaited: if that fetch resolved after the user had already
    // started editing the form but before they submitted, it silently
    // overwrote their in-progress edits with the stale pre-edit profile
    // -- the same navigate()-races-an-unawaited-fetch shape as the Log
    // view fix above, caught by a CI-only flake in Account_test.
    // AccountTest.test_editing_profile_fields_round_trips_without_touching_the_active_goal
    // (not reproducible locally). No legitimate reason for the profile
    // to have changed server-side between boot() and this navigation in
    // the first place, so the fetch was redundant, not just racy.
    fillProfileForm(document.getElementById("profile-form"), state.profile);
    // Phase 7.5 (Health Connect sync, see README): the "Data import,
    // export & sync" section (Export/Import/health sync) lives in the
    // Account view's markup, not Settings' (view-settings is only the
    // engine-constants form) -- this was previously wired to the
    // "settings" case below, which meant it silently never ran on an
    // Account visit; the section only ever appeared after some other
    // navigation happened to also visit Settings and unhide the shared
    // element from underneath the (still-active) Account view.
    refreshHealthSyncUI();
  }
  if (viewName === "report") refreshReport();
  if (viewName === "alert-history") refreshAlertHistory();
  if (viewName === "settings") {
    // Set synchronously, before the unawaited async refreshSettings()
    // below even starts -- getShowProjectedLogs() is a localStorage read,
    // not a fetch, so there's no legitimate reason to leave it sequenced
    // after refreshSettings()'s own network calls. Same
    // navigate()-races-an-unawaited-refresh shape already fixed for the
    // Log and Account views (see the Account case above and v2.0.1's
    // CHANGELOG entry) -- caught here by an intermittent CI/local
    // Playwright failure ("Clicking the checkbox did not change its
    // state") on Log_test.py's show-projected-preference tests.
    document.getElementById("settings-show-projected-logs").checked = getShowProjectedLogs();
    refreshSettings();
  }
}

async function refreshDashboardSummary() {
  const [latest, series, gainQuality, adherence, alerts, logs] = await Promise.all([
    api.metricsLatest().catch(() => null),
    api.metricsSeries().catch(() => []),
    api.gainQuality().catch(() => []),
    api.adherence().catch(() => null),
    api.alerts().catch(() => []),
    api.listLogs().catch(() => []),
  ]);
  state.series = series;
  state.gainQuality = gainQuality;
  state.latestMetrics = latest;

  const realSeries = series.filter((row) => row.source === "real");
  const previousMetrics = realSeries.length > 1 ? realSeries[realSeries.length - 2] : null;
  const realLogs = logs.filter((log) => log.source === "real");
  const latestRealLog = realLogs.length ? realLogs.reduce((a, b) => (b.date > a.date ? b : a)) : null;

  renderWeightSummary(
    document.getElementById("summary-weight-stats"),
    latest,
    previousMetrics,
    gainQuality[gainQuality.length - 1]
  );
  renderCaloriesSummary(
    document.getElementById("summary-calories-stats"),
    latest,
    adherence,
    latestRealLog
  );
  renderGoalSummary(document.getElementById("summary-goal-stats"), latest, state.profile);
  renderAlerts(document.getElementById("dashboard-alerts"), alerts);
  renderSexDisclaimer(document.getElementById("sex-disclaimer"), state.profile);
}

async function refreshDashboardCharts() {
  const [logs, goals, energyBalance, incrementAnalytics, tef, macroTargets] = await Promise.all([
    api.listLogs().catch(() => []),
    api.goals().catch(() => []),
    api.energyBalance().catch(() => []),
    api.incrementAnalytics().catch(() => []),
    api.tef().catch(() => []),
    api.macroTargets().catch(() => []),
  ]);
  state.dashboardData = { logs, goals, energyBalance, incrementAnalytics, tef, macroTargets };
  await renderDashboardCharts();
}

// Fetches a real+constant forecast for a given weeks-ahead count, cached per
// weeks value so re-toggling, re-rendering, or the Dashboard and Log view's
// toggles both wanting the same weeks value never re-hits the API twice.
async function fetchProjectionWeeks(weeks) {
  if (state.projectionCache[weeks]) return state.projectionCache[weeks];
  try {
    const rows = await api.projection(weeks, "real", "constant");
    state.projectionCache[weeks] = rows;
    return rows;
  } catch (err) {
    return [];
  }
}

async function renderDashboardCharts() {
  if (!state.dashboardData) return;
  const { logs, goals, energyBalance, incrementAnalytics, tef, macroTargets } = state.dashboardData;
  const series = state.series;
  const gainQuality = state.gainQuality;

  renderDashboardStats(
    document.getElementById("dashboard-stats"),
    state.latestMetrics,
    gainQuality[gainQuality.length - 1],
    energyBalance[energyBalance.length - 1],
    incrementAnalytics[incrementAnalytics.length - 1]
  );

  const logsById = new Map(logs.map((log) => [log.log_id, log]));
  const isProjected = (row) => row.source === "projected";

  // Phase 4.3: appending the forecast to a *copy* of the real series --
  // never `state.series` itself -- so the summary section and every other
  // chart below stay on real data only.
  const forecastRows = state.showProjection ? await fetchProjectionWeeks(state.projectionWeeks) : [];
  const forecastSeries = forecastRows.length ? series.concat(forecastRows) : series;
  const lastLoggedDate = series.length ? series[series.length - 1].date : null;
  const forecastMarkers =
    forecastRows.length && lastLoggedDate ? [{ date: lastLoggedDate, label: "Last logged" }] : [];

  drawLineChart(
    document.getElementById("chart-weight"),
    forecastSeries.map((row) => ({
      date: row.date,
      value: row.fat_mass_kg + row.lean_mass_kg,
      projected: row.source === "projected",
    })),
    { label: "Weight", markers: forecastMarkers }
  );
  drawLineChart(
    document.getElementById("chart-bodyfat"),
    forecastSeries.map((row) => ({
      date: row.date,
      value: row.body_fat * 100,
      projected: row.source === "projected",
    })),
    { label: "Body fat %", markers: forecastMarkers }
  );
  drawStackedBars(
    document.getElementById("chart-mass"),
    series.map((row) => ({ date: row.date, fat: row.fat_mass_kg, lean: row.lean_mass_kg }))
  );
  drawLineChart(
    document.getElementById("chart-calories"),
    forecastSeries.map((row) => ({
      date: row.date,
      value: row.target_calories,
      projected: row.source === "projected",
    })),
    { label: "Target calories", markers: forecastMarkers }
  );
  drawMultiLineChart(
    document.getElementById("chart-perimeters"),
    forecastSeries,
    [
      {
        accessor: (row) => {
          const log = logsById.get(row.log_id);
          return log ? log.waist_cm : row.estimated_waist || 0;
        },
        color: "#5eb3ff",
        label: "Waist",
      },
      {
        accessor: (row) => {
          const log = logsById.get(row.log_id);
          return log ? log.neck_cm : row.estimated_neck || 0;
        },
        color: "#f0b94d",
        label: "Neck",
      },
    ],
    { isProjected, markers: forecastMarkers }
  );
  drawLineChart(
    document.getElementById("chart-steps"),
    series.map((row) => ({
      date: row.date,
      value: (logsById.get(row.log_id) || {}).steps || 0,
      projected: row.source === "projected",
    })),
    { label: "Steps" }
  );

  // A goal's start_date is set from the real wall-clock date it was
  // created/changed, which can fall after the last logged week (e.g. the
  // very first goal, dated at registration). Previously that always
  // landed off the chart's real-only date domain and got silently
  // clamped to the right edge; now that the forecast toggle can widen the
  // domain past it, it would otherwise reappear mid-chart looking like an
  // unrelated second "Last logged" line -- so it's excluded once it's no
  // longer describing a change within the real data itself.
  const goalMarkers = goals
    .filter((goal) => !lastLoggedDate || goal.start_date <= lastLoggedDate)
    .map((goal) => ({
      date: goal.start_date,
      label: `Plan changed: target BF ${(goal.target_bf * 100).toFixed(1)}%, rate ${(
        goal.weekly_rate * 100
      ).toFixed(2)}%/wk`,
    }));
  drawMultiLineChart(
    document.getElementById("chart-goal-trajectory"),
    forecastSeries,
    [
      { accessor: (row) => row.fat_mass_kg + row.lean_mass_kg, color: "#5eb3ff", label: "Actual" },
      {
        accessor: (row) => row.weight_objective_kg,
        color: "#7ee787",
        dashed: true,
        label: "Target",
      },
    ],
    { isProjected, markers: [...goalMarkers, ...forecastMarkers] }
  );

  drawDivergingBars(
    document.getElementById("chart-gain-quality"),
    gainQuality.map((row) => ({
      date: row.date,
      fat: row.delta_fat_kg,
      lean: row.delta_lean_kg,
    }))
  );

  const reconciledWeeks = energyBalance.filter(
    (row) => row.surplus_ingested_kcal != null && row.surplus_tissue_kcal != null
  );
  drawMultiLineChart(
    document.getElementById("chart-energy-balance"),
    reconciledWeeks,
    [
      { accessor: (row) => row.surplus_ingested_kcal, color: "#5eb3ff", label: "Ingested" },
      { accessor: (row) => row.surplus_tissue_kcal, color: "#f0b94d", label: "Tissue" },
    ]
  );

  drawMultiLineChart(
    document.getElementById("chart-increment-analytics"),
    incrementAnalytics,
    [
      { accessor: (row) => row.incr_real_pct * 100, color: "#5eb3ff", label: "Actual" },
      {
        accessor: (row) => row.goal_weekly_rate * 100,
        color: "#7ee787",
        dashed: true,
        label: "Goal rate",
      },
    ]
  );

  const macroWeeks = tef.filter((row) => row.tef_kcal_macros != null);
  drawMultiLineChart(
    document.getElementById("chart-tef"),
    macroWeeks,
    [
      { accessor: (row) => row.tef_kcal_flat, color: "#5eb3ff", label: "Flat estimate" },
      { accessor: (row) => row.tef_kcal_macros, color: "#f0b94d", label: "From macros" },
    ]
  );

  const latestMacroTargets = macroTargets[macroTargets.length - 1];
  const macroBars = latestMacroTargets
    ? [
        {
          label: "Target",
          segments: [
            { label: "Protein", value: latestMacroTargets.protein_target_kcal, color: MACRO_COLORS.protein },
            { label: "Fat", value: latestMacroTargets.fat_target_kcal, color: MACRO_COLORS.fat },
            { label: "Carbs", value: latestMacroTargets.carbs_target_kcal, color: MACRO_COLORS.carbs },
          ],
        },
        ...(latestMacroTargets.has_actual
          ? [
              {
                label: "Actual",
                segments: [
                  { label: "Protein", value: latestMacroTargets.protein_actual_kcal, color: MACRO_COLORS.protein },
                  { label: "Fat", value: latestMacroTargets.fat_actual_kcal, color: MACRO_COLORS.fat },
                  { label: "Carbs", value: latestMacroTargets.carbs_actual_kcal, color: MACRO_COLORS.carbs },
                ],
              },
            ]
          : []),
      ]
    : [];
  drawMacroSplitBars(document.getElementById("chart-macro-split"), macroBars);
}

async function refreshLogs() {
  state.logs = await api.listLogs();
  resetWizardDefaults();
  renderLogNav();
  renderFilteredLogList();
  refreshProjectedRow();
  goToLogStep(1);
}

// Sets the wizard's granularity default from the active view mode (day ->
// daily, week -> weekly) -- only called at "fresh wizard" points (entering
// the Log view, switching day/week, and after a successful save) so it
// never clobbers a manual choice mid-entry.
function resetWizardGranularityDefault() {
  document.getElementById("log-wizard-granularity").value =
    state.logNav.viewMode === "week" ? "weekly" : "daily";
}

// Phase 7.4 (partial logs, see README): the most recent real log isn't
// necessarily the most recent one with perimeters -- e.g. a synced,
// steps-only day is "real" but has no waist/neck yet. Prefill from
// whichever recent real log actually has them.
function mostRecentLogWithPerimeters() {
  const withPerimeters = state.logs.filter(
    (log) => log.source === "real" && log.waist_cm != null && log.neck_cm != null
  );
  return withPerimeters.length
    ? withPerimeters.reduce((a, b) => (b.date > a.date ? b : a))
    : null;
}

// Most weeks a person's waist/neck barely change, so the wizard opens
// pre-filled from the account's last real log -- weight stays blank since
// it's the one number that's supposed to change and get re-measured every
// time, and intake/steps/cardio/macros stay blank too (today's actual
// entry, not a carry-forward).
function prefillWizardFromLastLog() {
  const lastLog = mostRecentLogWithPerimeters();
  const form = document.getElementById("log-form");
  form.waist_cm.value = lastLog ? lastLog.waist_cm : "";
  form.neck_cm.value = lastLog ? lastLog.neck_cm : "";
}

// Every "fresh wizard" reset point (entering the Log view, switching
// day/week) resets both the granularity default and the perimeter prefill
// together.
function resetWizardDefaults() {
  resetWizardGranularityDefault();
  prefillWizardFromLastLog();
}

// Phase 7.4 (partial logs, see README): a log opened for editing can be
// missing weight/waist/neck/intake/steps (e.g. a Health Connect sync
// wrote steps/nutrition but nobody's added body measurements yet) -- each
// falls back to an empty input, same as the macro fields already did,
// rather than the literal string "null".
function fillWizardFromLog(log) {
  const form = document.getElementById("log-form");
  form.weight_kg.value = log.weight_kg == null ? "" : log.weight_kg;
  form.waist_cm.value = log.waist_cm == null ? "" : log.waist_cm;
  form.neck_cm.value = log.neck_cm == null ? "" : log.neck_cm;
  form.intake_kcal.value = log.intake_kcal == null ? "" : log.intake_kcal;
  form.steps.value = log.steps == null ? "" : log.steps;
  form.cardio_kcal.value = log.cardio_kcal == null ? "" : log.cardio_kcal;
  form.carbs_g.value = log.carbs_g == null ? "" : log.carbs_g;
  form.fat_g.value = log.fat_g == null ? "" : log.fat_g;
  form.protein_g.value = log.protein_g == null ? "" : log.protein_g;
  form.granularity.value = log.granularity;
}

// Phase 5.7: a log's date and granularity are not editable -- the wizard's
// date label/hidden input are pinned to the log's own date (instead of the
// navigator's selected day/week) and the granularity select is disabled,
// both restored by exitEditMode(). Every other field stays editable.
function enterEditMode(log) {
  state.editingLogId = log.log_id;
  fillWizardFromLog(log);
  document.getElementById("log-wizard-granularity").disabled = true;
  document.getElementById("log-wizard-date-input").value = log.date;
  document.getElementById("log-wizard-date-prefix").textContent = "Editing log for";
  document.getElementById("log-wizard-date-label").textContent = formatDayLabel(log.date);
  document.getElementById("log-save").textContent = "Save changes";
  document.getElementById("log-cancel-edit").hidden = false;
  goToLogStep(1);
}

// Only clears edit-mode's own UI flags -- callers (Cancel, or a successful
// edit save via refreshLogs()) are responsible for restoring the form and
// wizard nav themselves, same as the create-mode reset they already do.
function exitEditMode() {
  state.editingLogId = null;
  document.getElementById("log-wizard-granularity").disabled = false;
  document.getElementById("log-save").textContent = "Save log";
  document.getElementById("log-cancel-edit").hidden = true;
}

function renderLogNav() {
  const { selectedDate, viewMode } = state.logNav;
  const isWeek = viewMode === "week";

  document.getElementById("log-nav-label").textContent = isWeek
    ? formatWeekLabel(selectedDate)
    : formatDayLabel(selectedDate);
  document.getElementById("log-nav-date").value = selectedDate;
  document.getElementById("log-nav-day").classList.toggle("active", !isWeek);
  document.getElementById("log-nav-week").classList.toggle("active", isWeek);

  // While editing an existing log, the wizard's date is bound to that log's
  // own date (set by enterEditMode), not the navigator's selected day/week.
  if (state.editingLogId == null) {
    document.getElementById("log-wizard-date-prefix").textContent = "Logging for";
    document.getElementById("log-wizard-date-input").value = selectedDate;
    document.getElementById("log-wizard-date-label").textContent = isWeek
      ? formatWeekLabel(selectedDate)
      : formatDayLabel(selectedDate);
  }

  const heading = document.getElementById("log-list-heading");
  if (isWeek) {
    const thisWeek = isoWeekRange(todayIso()).start === isoWeekRange(selectedDate).start;
    heading.textContent = thisWeek ? "This week's logs" : `Logs for ${formatWeekLabel(selectedDate)}`;
  } else {
    heading.textContent = selectedDate === todayIso() ? "Today's logs" : `Logs for ${formatDayLabel(selectedDate)}`;
  }
}

function filteredLogs() {
  const { selectedDate, viewMode } = state.logNav;
  if (viewMode === "week") {
    const { start, end } = isoWeekRange(selectedDate);
    return state.logs.filter((log) => log.date >= start && log.date <= end);
  }
  // A "weekly" log represents its whole ISO week (Mon-Sun), the same
  // grouping LogResampler.resample_to_weekly uses server-side -- so it
  // should appear on every day of that week in day view, not just its
  // own literal logged date (which is often the day it happened to be
  // entered, e.g. a Sunday). A "daily" log still only matches its own
  // exact date, since it genuinely represents just that one day.
  return state.logs.filter((log) => {
    if (log.granularity === "weekly") {
      const { start, end } = isoWeekRange(log.date);
      return selectedDate >= start && selectedDate <= end;
    }
    return log.date === selectedDate;
  });
}

function renderFilteredLogList(extraRow) {
  const rows = extraRow ? filteredLogs().concat(extraRow) : filteredLogs();
  document.getElementById("log-table").hidden = rows.length === 0;
  document.getElementById("log-list-empty").hidden = rows.length !== 0;
  renderLogTable(document.querySelector("#log-table tbody"), rows);
}

function setLogNav(patch) {
  Object.assign(state.logNav, patch);
  renderLogNav();
  renderFilteredLogList();
  refreshProjectedRow();
}

function lastRealLoggedDate() {
  const realDates = state.logs.filter((log) => log.source === "real").map((log) => log.date);
  return realDates.length ? realDates.reduce((a, b) => (b > a ? b : a)) : null;
}

function weeksBetween(fromIso, toIso) {
  const [fy, fm, fd] = fromIso.split("-").map(Number);
  const [ty, tm, td] = toIso.split("-").map(Number);
  const days = (new Date(ty, tm - 1, td) - new Date(fy, fm - 1, fd)) / 86400000;
  return Math.ceil(days / 7);
}

// toFixed (not Math.round(x*10)/10) so a whole-number estimate still shows
// one decimal place (e.g. "88.0"), not "88".
function round1(value) {
  return value.toFixed(1);
}

// A row from GET /api/projection has no intake/steps/cardio/macros --
// those are engine *inputs* the forecast never observed, not outputs it
// computed -- so they're left null and renderLogTable dashes them, same
// table/columns as a real log, with log_id null (nothing to delete)
// marking it as never persisted. Granularity is always "weekly" since the
// forecast itself is weekly-cadence (Phase 4.3), regardless of the Log
// view's own day/week toggle.
function projectedLogRow(row) {
  return {
    log_id: null,
    date: row.date,
    weight_kg: round1(row.estimated_weight),
    waist_cm: round1(row.estimated_waist),
    neck_cm: round1(row.estimated_neck),
    intake_kcal: null,
    steps: null,
    cardio_kcal: null,
    carbs_g: null,
    fat_g: null,
    protein_g: null,
    source: "projected",
    granularity: "weekly",
  };
}

// Phase 4.5: injects a projected row straight into the Log table (not a
// separate widget) when the "Show projected" browser preference (Settings
// view, localStorage) is on and the navigated day/week has no log yet and
// falls after the last *real* logged date -- the forecast stays weekly
// (never a fabricated daily figure), so a day-view lookup finds the
// forecasted week covering that day, same as week view's own ISO-week match.
async function refreshProjectedRow() {
  if (!getShowProjectedLogs() || filteredLogs().length > 0) return;
  const lastReal = lastRealLoggedDate();
  const { selectedDate, viewMode } = state.logNav;
  const { start, end } = isoWeekRange(selectedDate);
  const targetDate = viewMode === "week" ? end : selectedDate;
  if (!lastReal || targetDate <= lastReal) return;
  const weeks = Math.min(52, Math.max(1, weeksBetween(lastReal, targetDate)));
  const rows = await fetchProjectionWeeks(weeks);
  const row = rows.find((r) => r.date >= start && r.date <= end) || rows[rows.length - 1];
  if (!row) return;
  // The user may have navigated elsewhere while this was in flight -- don't
  // let a stale response render onto the wrong day/week.
  if (state.logNav.selectedDate !== selectedDate || state.logNav.viewMode !== viewMode) return;
  renderFilteredLogList(projectedLogRow(row));
}

function goToLogStep(step) {
  logWizardStep = step;
  const form = document.getElementById("log-form");
  showWizardStep(form, step, LOG_WIZARD_STEPS);
  if (step === LOG_WIZARD_STEPS) {
    const values = formToJson(form);
    // The granularity <select> is disabled while editing, so FormData
    // excludes it -- pull it back in from the log being edited for display.
    if (state.editingLogId != null) {
      const editing = state.logs.find((log) => log.log_id === state.editingLogId);
      if (editing) values.granularity = editing.granularity;
    }
    renderLogReview(document.getElementById("log-review"), values);
  }
}

function currentLogStepIsValid() {
  const fieldset = document.querySelector(`.wizard-step[data-step="${logWizardStep}"]`);
  return Array.from(fieldset.querySelectorAll("input")).every((input) =>
    input.reportValidity()
  );
}

async function refreshPlan() {
  const [profile, current, goals] = await Promise.all([
    api.me(),
    api.metricsLatest().catch(() => null),
    api.goals().catch(() => []),
  ]);
  state.profile = profile;
  const form = document.getElementById("plan-form");
  form.target_bf_pct.value = (profile.target_bf * 100).toFixed(1);
  form.weekly_rate_pct.value = (profile.weekly_rate * 100).toFixed(2);
  renderPlanStats(document.getElementById("plan-current-stats"), current, profile.direction);
  renderGoalHistory(document.querySelector("#goal-history-table tbody"), goals);

  // Phase 8.1: the active goal's start date is only editable bounded
  // strictly after whichever prior goal most recently ended, mirroring
  // GoalPlanManager.update_start_date's own server-side bounds.
  const activeGoal = goals.find((goal) => goal.active);
  document.getElementById("goal-start-date-section").hidden = !activeGoal;
  if (activeGoal) {
    const previousGoal = goals
      .filter((goal) => !goal.active)
      .reduce((latest, goal) => (!latest || goal.start_date > latest.start_date ? goal : latest), null);
    const startDateInput = document.getElementById("goal-start-date-input");
    startDateInput.value = activeGoal.start_date;
    startDateInput.min = previousGoal ? addDays(previousGoal.start_date, 1) : "";
    startDateInput.max = todayIso();
  }

  state.planPreviewParams = null;
  document.getElementById("plan-preview-result").hidden = true;
  setFormError("plan-form", "");
  setFormError("plan-commit", "");
  setFormError("goal-start-date-form", "");
}

async function refreshReport() {
  const report = await api.report();
  renderReport(document.getElementById("report-content"), report);
}

async function refreshAlertHistory() {
  const alerts = await api.alerts(true);
  renderAlertHistory(document.getElementById("alert-history-list"), alerts);
}

async function refreshSettings() {
  const [settings, history] = await Promise.all([api.getSettings(), api.settingsHistory()]);
  fillSettingsForm(document.getElementById("settings-form"), settings);
  renderSettingsStatus(document.getElementById("settings-status"), settings);
  renderSettingsHistory(document.querySelector("#settings-history-table tbody"), history);
  setFormError("settings-form", "");
}

// Phase 7.5 (Health Connect sync, see README): Android app only -- a no-op
// (section stays hidden) on the web build and any device where the native
// plugin isn't available.
const HEALTH_SYNC_DEFAULT_WINDOW_DAYS = 7;
const HEALTH_SYNC_LAST_SYNCED_KEY = "healthSyncLastSyncedAt";

// Falls back to the default for a blank/invalid/out-of-range value rather
// than rejecting it outright -- this is a convenience field, not a form
// that needs its own error state.
function healthSyncWindowDays() {
  const raw = Number(document.getElementById("health-sync-days-input").value);
  if (!Number.isFinite(raw) || raw < 1) return HEALTH_SYNC_DEFAULT_WINDOW_DAYS;
  return Math.min(raw, 90);
}

async function refreshHealthSyncUI() {
  const section = document.getElementById("health-sync-section");
  if (!healthSync.isSupported()) {
    section.hidden = true;
    return;
  }
  section.hidden = false;
  const permissions = await healthSync.hasPermissions();
  const lastSyncedAt = localStorage.getItem(HEALTH_SYNC_LAST_SYNCED_KEY);
  renderHealthSyncStatus(document.getElementById("health-sync-status"), permissions, lastSyncedAt);
}

document.getElementById("health-connect-btn").addEventListener("click", async () => {
  await healthSync.requestPermissions();
  await refreshHealthSyncUI();
});

// Pressing "Sync now" calls PUT /api/logs/by-date once per source (steps,
// nutrition), independently, for every returned day -- so Mi Fitness
// failing/being disconnected never blocks Samsung Health's write, and vice
// versa (README's Phase 7.4/7.5). Macros are only sent as a trio (never
// partially), matching validate_log_input's all-or-nothing rule -- a day
// with e.g. only carbs_g from Health Connect just doesn't send macros that
// day, rather than getting rejected outright. healthSync.syncRecentReadings
// already rounds every numeric field to 1 decimal, so what's read here is
// what gets stored.
document.getElementById("health-sync-now-btn").addEventListener("click", async () => {
  const summaryEl = document.getElementById("health-sync-summary");
  summaryEl.textContent = "Syncing…";
  try {
    const sinceDate = addDays(todayIso(), -healthSyncWindowDays());
    const { readings } = await healthSync.syncRecentReadings(sinceDate);
    let stepsCount = 0;
    let nutritionCount = 0;
    for (const reading of readings) {
      if (reading.steps != null) {
        await api.upsertLogByDate(reading.date, { steps: reading.steps, granularity: "daily" });
        stepsCount++;
      }
      const nutritionFields = {};
      if (reading.intake_kcal != null) nutritionFields.intake_kcal = reading.intake_kcal;
      if (reading.carbs_g != null && reading.fat_g != null && reading.protein_g != null) {
        nutritionFields.carbs_g = reading.carbs_g;
        nutritionFields.fat_g = reading.fat_g;
        nutritionFields.protein_g = reading.protein_g;
      }
      if (Object.keys(nutritionFields).length > 0) {
        nutritionFields.granularity = "daily";
        await api.upsertLogByDate(reading.date, nutritionFields);
        nutritionCount++;
      }
    }
    localStorage.setItem(HEALTH_SYNC_LAST_SYNCED_KEY, new Date().toISOString());
    summaryEl.textContent = `Synced ${stepsCount} day(s) of steps, ${nutritionCount} day(s) of nutrition.`;
    await refreshHealthSyncUI();
    await refreshLogs();
  } catch (err) {
    summaryEl.textContent = `Sync failed: ${err.message}`;
  }
});

function formToJson(form) {
  return Object.fromEntries(new FormData(form).entries());
}

navButtons.forEach((btn) => {
  btn.addEventListener("click", () => navigate(btn.dataset.view));
});

logoutBtn.addEventListener("click", async () => {
  try {
    await api.logout();
  } finally {
    clearToken();
    showAuthOnly();
  }
});

document.getElementById("login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  setFormError("login-form", "");
  const payload = formToJson(event.target);
  try {
    const { token, profile } = await api.login(payload);
    setToken(token);
    state.profile = profile;
    await enterApp();
  } catch (err) {
    setFormError("login-form", err.message);
  }
});

document.getElementById("forgot-password-toggle").addEventListener("click", () => {
  const container = document.getElementById("password-recovery");
  container.hidden = !container.hidden;
});

document.getElementById("reset-password-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  setFormError("reset-password-form", "");
  document.getElementById("reset-password-note").textContent = "";
  const raw = formToJson(event.target);
  try {
    const { message } = await api.resetPassword(raw.identifier, raw.new_password);
    document.getElementById("reset-password-note").textContent = message;
    event.target.reset();
  } catch (err) {
    setFormError("reset-password-form", err.message);
  }
});

document.getElementById("register-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  setFormError("register-form", "");
  const raw = formToJson(event.target);
  const payload = {
    username: raw.username,
    email: raw.email,
    password: raw.password,
    height_cm: Number(raw.height_cm),
    sex: Number(raw.sex),
    birthdate: raw.birthdate,
  };
  try {
    const { token, profile } = await api.register(payload);
    setToken(token);
    state.profile = profile;
    await enterApp();
  } catch (err) {
    setFormError("register-form", err.message);
  }
});

document.getElementById("log-nav-prev").addEventListener("click", () => {
  const step = state.logNav.viewMode === "week" ? 7 : 1;
  setLogNav({ selectedDate: addDays(state.logNav.selectedDate, -step) });
});

document.getElementById("log-nav-next").addEventListener("click", () => {
  const step = state.logNav.viewMode === "week" ? 7 : 1;
  setLogNav({ selectedDate: addDays(state.logNav.selectedDate, step) });
});

document.getElementById("log-nav-day").addEventListener("click", () => {
  state.logNav.viewMode = "day";
  resetWizardDefaults();
  renderLogNav();
  renderFilteredLogList();
  refreshProjectedRow();
});

document.getElementById("log-nav-week").addEventListener("click", () => {
  state.logNav.viewMode = "week";
  resetWizardDefaults();
  renderLogNav();
  renderFilteredLogList();
  refreshProjectedRow();
});

document.getElementById("log-nav-date").addEventListener("change", (event) => {
  if (event.target.value) setLogNav({ selectedDate: event.target.value });
});

document.getElementById("log-next").addEventListener("click", () => {
  if (!currentLogStepIsValid()) return;
  goToLogStep(Math.min(logWizardStep + 1, LOG_WIZARD_STEPS));
});

document.getElementById("log-back").addEventListener("click", () => {
  goToLogStep(Math.max(logWizardStep - 1, 1));
});

function optionalNumber(raw) {
  return raw === "" || raw == null ? null : Number(raw);
}

document.getElementById("log-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  setFormError("log-form", "");
  const raw = formToJson(event.target);
  // Shared by create and edit; date/granularity are only ever sent when
  // creating -- edit mode omits them so the server's partial-update
  // semantics (log_routes.py's update_log) leave them untouched, since
  // neither is editable here.
  // Phase 7.4 (partial logs, see README): weight/waist/neck/intake/steps
  // are all optional now, same treatment the macro trio already had --
  // a blank field means "not logged," sent as null, not coerced to 0.
  // cardio_kcal is the one exception: it stays a real 0-or-a-number
  // field (the server column is still NOT NULL DEFAULT 0), matching its
  // own input's "0" default.
  const measurements = {
    weight_kg: optionalNumber(raw.weight_kg),
    waist_cm: optionalNumber(raw.waist_cm),
    neck_cm: optionalNumber(raw.neck_cm),
    intake_kcal: optionalNumber(raw.intake_kcal),
    steps: optionalNumber(raw.steps),
    cardio_kcal: Number(raw.cardio_kcal) || 0,
    carbs_g: optionalNumber(raw.carbs_g),
    fat_g: optionalNumber(raw.fat_g),
    protein_g: optionalNumber(raw.protein_g),
  };
  try {
    if (state.editingLogId != null) {
      await api.updateLog(state.editingLogId, measurements);
      exitEditMode();
    } else {
      await api.createLog({
        ...measurements,
        date: raw.date,
        granularity: raw.granularity || "weekly",
      });
    }
    event.target.reset();
    await refreshLogs();
  } catch (err) {
    setFormError("log-form", err.message);
  }
});

document.getElementById("log-cancel-edit").addEventListener("click", () => {
  exitEditMode();
  document.getElementById("log-form").reset();
  resetWizardDefaults();
  renderLogNav();
  goToLogStep(1);
});

document.querySelector("#log-table tbody").addEventListener("click", async (event) => {
  const deleteBtn = event.target.closest(".delete-log-btn");
  if (deleteBtn) {
    await api.deleteLog(deleteBtn.dataset.logId);
    await refreshLogs();
    return;
  }
  const editBtn = event.target.closest(".edit-log-btn");
  if (editBtn) {
    const log = state.logs.find((l) => l.log_id === Number(editBtn.dataset.logId));
    if (log) enterEditMode(log);
  }
});

document.getElementById("dashboard-alerts").addEventListener("click", async (event) => {
  const btn = event.target.closest(".alert-dismiss-btn");
  if (!btn) return;
  await api.acknowledgeAlert(btn.dataset.alertId);
  await refreshDashboardSummary();
});

document.getElementById("dashboard-details").addEventListener("toggle", (event) => {
  if (event.target.open && !state.dashboardChartsLoaded) {
    state.dashboardChartsLoaded = true;
    refreshDashboardCharts();
  }
});

document.getElementById("dashboard-projection-toggle")?.addEventListener("change", (event) => {
  state.showProjection = event.target.checked;
  if (state.dashboardChartsLoaded) renderDashboardCharts();
});

document.getElementById("dashboard-projection-weeks")?.addEventListener("change", (event) => {
  state.projectionWeeks = Number(event.target.value);
  if (state.showProjection && state.dashboardChartsLoaded) renderDashboardCharts();
});

document.getElementById("report-print-btn").addEventListener("click", () => {
  window.print();
});

document.getElementById("goal-start-date-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  setFormError("goal-start-date-form", "");
  const startDate = document.getElementById("goal-start-date-input").value;
  try {
    await api.updateGoalStartDate(startDate);
    await refreshPlan();
  } catch (err) {
    setFormError("goal-start-date-form", err.message);
  }
});

document.getElementById("plan-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  setFormError("plan-form", "");
  setFormError("plan-commit", "");
  const raw = formToJson(event.target);
  const params = {
    target_bf: Number(raw.target_bf_pct) / 100,
    weekly_rate: Number(raw.weekly_rate_pct) / 100,
  };
  try {
    const proposed = await api.planPreview(params);
    state.planPreviewParams = params;
    const direction = params.weekly_rate > 0 ? "bulk" : "cut";
    renderPlanStats(document.getElementById("plan-proposed-stats"), proposed, direction);
    document.getElementById("plan-preview-result").hidden = false;
  } catch (err) {
    state.planPreviewParams = null;
    document.getElementById("plan-preview-result").hidden = true;
    setFormError("plan-form", err.message);
  }
});

document.getElementById("plan-commit-btn").addEventListener("click", async () => {
  if (!state.planPreviewParams) return;
  setFormError("plan-commit", "");
  try {
    state.profile = await api.updateProfile(state.planPreviewParams);
    await refreshPlan();
  } catch (err) {
    setFormError("plan-commit", err.message);
  }
});

document.getElementById("profile-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  setFormError("profile-form", "");
  const raw = formToJson(event.target);
  const payload = {
    height_cm: Number(raw.height_cm),
    sex: Number(raw.sex),
    birthdate: raw.birthdate,
  };
  try {
    state.profile = await api.updateProfile(payload);
  } catch (err) {
    setFormError("profile-form", err.message);
  }
});

document.getElementById("password-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  setFormError("password-form", "");
  const raw = formToJson(event.target);
  try {
    await api.changePassword({ old_password: raw.old_password, new_password: raw.new_password });
    event.target.reset();
  } catch (err) {
    setFormError("password-form", err.message);
  }
});

document.getElementById("export-btn").addEventListener("click", async () => {
  const data = await api.exportData();
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "justfitting-export.json";
  a.click();
  URL.revokeObjectURL(url);
});

document.getElementById("import-input").addEventListener("change", async (event) => {
  const file = event.target.files[0];
  if (!file) return;
  const summaryEl = document.getElementById("import-summary");
  try {
    const text = await file.text();
    const payload = file.name.toLowerCase().endsWith(".csv")
      ? parseCsvLogs(text)
      : JSON.parse(text);
    const result = await api.importData(payload);
    renderImportSummary(summaryEl, result);
    await refreshLogs();
  } catch (err) {
    summaryEl.textContent = `Import failed: ${err.message}`;
  }
  event.target.value = "";
});

document.getElementById("delete-account-btn").addEventListener("click", async () => {
  if (!confirm("This permanently deletes your account and all logs. Continue?")) return;
  await api.deleteAccount();
  clearToken();
  showAuthOnly();
});

document.getElementById("alert-history-list").addEventListener("click", async (event) => {
  const btn = event.target.closest(".alert-dismiss-btn");
  if (!btn) return;
  await api.acknowledgeAlert(btn.dataset.alertId);
  await refreshAlertHistory();
});

document.getElementById("settings-show-projected-logs").addEventListener("change", (event) => {
  setShowProjectedLogs(event.target.checked);
});

document.getElementById("settings-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  setFormError("settings-form", "");
  const raw = formToJson(event.target);
  const payload = {
    tef: Number(raw.tef_pct) / 100,
    kcal_per_kg_fat: Number(raw.kcal_per_kg_fat),
    neat_step_factor: Number(raw.neat_step_factor),
    implausible_weekly_change_pct: Number(raw.implausible_pct) / 100,
    stagnation_weeks: Number(raw.stagnation_weeks),
    stagnation_threshold_kg: Number(raw.stagnation_threshold_kg),
    lean_loss_window_weeks: Number(raw.lean_loss_window_weeks),
    max_lean_mass_loss_share: Number(raw.max_lean_loss_pct) / 100,
    significant_deviation_kg: Number(raw.significant_deviation_kg),
    bmr_model: raw.bmr_model,
    w_rfm: Number(raw.w_rfm),
    w_navy: Number(raw.w_navy),
    w_deur: Number(raw.w_deur),
    delta: Number(raw.delta_pct) / 100,
    ffmi_coef: Number(raw.ffmi_coef),
    lean_tissue_kcal_per_kg: Number(raw.lean_tissue_kcal_per_kg),
    fat_ratio_ideal: Number(raw.fat_ratio_ideal_pct) / 100,
    reconciliation_error_threshold_kcal: Number(raw.reconciliation_error_threshold_kcal),
    tef_mode: raw.tef_mode,
    kappa_carbs: Number(raw.kappa_carbs),
    kappa_fat: Number(raw.kappa_fat),
    kappa_protein: Number(raw.kappa_protein),
    macro_kcal_mismatch_pct: Number(raw.macro_mismatch_pct) / 100,
    protein_target_g_per_kg: Number(raw.protein_target_g_per_kg),
    fat_target_g_per_kg: Number(raw.fat_target_g_per_kg),
    macro_target_deviation_pct: Number(raw.macro_target_deviation_pct) / 100,
  };
  try {
    await api.updateSettings(payload);
    await refreshSettings();
  } catch (err) {
    setFormError("settings-form", err.message);
  }
});

boot();
