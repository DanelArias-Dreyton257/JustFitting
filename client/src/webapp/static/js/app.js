// Controller: holds all app state, wires DOM events to api.js and views.js.
import { api } from "./api.js";
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
  if (viewName === "log") refreshLogs();
  if (viewName === "plan") refreshPlan();
  if (viewName === "account") refreshAccount();
  if (viewName === "report") refreshReport();
  if (viewName === "alert-history") refreshAlertHistory();
  if (viewName === "settings") refreshSettings();
}

async function refreshDashboardSummary() {
  const [latest, series, gainQuality, adherence, alerts] = await Promise.all([
    api.metricsLatest().catch(() => null),
    api.metricsSeries().catch(() => []),
    api.gainQuality().catch(() => []),
    api.adherence().catch(() => null),
    api.alerts().catch(() => []),
  ]);
  state.series = series;
  state.gainQuality = gainQuality;
  state.latestMetrics = latest;

  const realSeries = series.filter((row) => row.source === "real");
  const previousMetrics = realSeries.length > 1 ? realSeries[realSeries.length - 2] : null;

  renderWeightSummary(
    document.getElementById("summary-weight-stats"),
    latest,
    previousMetrics,
    gainQuality[gainQuality.length - 1]
  );
  renderCaloriesSummary(document.getElementById("summary-calories-stats"), latest, adherence);
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
  resetWizardGranularityDefault();
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

function renderLogNav() {
  const { selectedDate, viewMode } = state.logNav;
  const isWeek = viewMode === "week";

  document.getElementById("log-nav-label").textContent = isWeek
    ? formatWeekLabel(selectedDate)
    : formatDayLabel(selectedDate);
  document.getElementById("log-nav-date").value = selectedDate;
  document.getElementById("log-nav-day").classList.toggle("active", !isWeek);
  document.getElementById("log-nav-week").classList.toggle("active", isWeek);

  document.getElementById("log-wizard-date-input").value = selectedDate;
  document.getElementById("log-wizard-date-label").textContent = isWeek
    ? formatWeekLabel(selectedDate)
    : formatDayLabel(selectedDate);

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
  return state.logs.filter((log) => log.date === selectedDate);
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
    renderLogReview(document.getElementById("log-review"), formToJson(form));
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
  state.planPreviewParams = null;
  document.getElementById("plan-preview-result").hidden = true;
  setFormError("plan-form", "");
  setFormError("plan-commit", "");
}

async function refreshAccount() {
  const profile = await api.me();
  state.profile = profile;
  fillProfileForm(document.getElementById("profile-form"), profile);
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
  document.getElementById("settings-show-projected-logs").checked = getShowProjectedLogs();
}

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
    target_bf: Number(raw.target_bf_pct) / 100,
    weekly_rate: Number(raw.weekly_rate_pct) / 100,
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
  resetWizardGranularityDefault();
  renderLogNav();
  renderFilteredLogList();
  refreshProjectedRow();
});

document.getElementById("log-nav-week").addEventListener("click", () => {
  state.logNav.viewMode = "week";
  resetWizardGranularityDefault();
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
  const payload = {
    date: raw.date,
    weight_kg: Number(raw.weight_kg),
    waist_cm: Number(raw.waist_cm),
    neck_cm: Number(raw.neck_cm),
    intake_kcal: Number(raw.intake_kcal),
    steps: Number(raw.steps),
    cardio_kcal: Number(raw.cardio_kcal) || 0,
    granularity: raw.granularity || "weekly",
    carbs_g: optionalNumber(raw.carbs_g),
    fat_g: optionalNumber(raw.fat_g),
    protein_g: optionalNumber(raw.protein_g),
  };
  try {
    await api.createLog(payload);
    event.target.reset();
    await refreshLogs();
  } catch (err) {
    setFormError("log-form", err.message);
  }
});

document.querySelector("#log-table tbody").addEventListener("click", async (event) => {
  const btn = event.target.closest(".delete-log-btn");
  if (!btn) return;
  await api.deleteLog(btn.dataset.logId);
  await refreshLogs();
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
    target_bf: Number(raw.target_bf_pct) / 100,
    weekly_rate: Number(raw.weekly_rate_pct) / 100,
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
  const text = await file.text();
  const payload = JSON.parse(text);
  await api.importData(payload);
  await refreshLogs();
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
