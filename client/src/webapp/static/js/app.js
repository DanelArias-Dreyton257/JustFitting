// Controller: holds all app state, wires DOM events to api.js and views.js.
import { api } from "./api.js";
import { getToken, setToken, clearToken, isAuthenticated } from "./session.js";
import {
  showView,
  setFormError,
  renderDashboardStats,
  renderAlerts,
  renderAlertHistory,
  renderGoalHistory,
  renderLogTable,
  renderProjectionTable,
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
} from "./charts.js";

const state = {
  profile: null,
  logs: [],
  series: [],
  planPreviewParams: null,
};

const LOG_WIZARD_STEPS = 4;
let logWizardStep = 1;

const navButtons = document.querySelectorAll(".nav-link");
const logoutBtn = document.getElementById("logout-btn");

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
  showView("auth");
}

async function enterApp() {
  navButtons.forEach((btn) => (btn.hidden = false));
  logoutBtn.hidden = false;
  navigate("dashboard");
}

function navigate(viewName) {
  showView(viewName);
  if (viewName === "dashboard") refreshDashboard();
  if (viewName === "log") refreshLogs();
  if (viewName === "projection") refreshProjection();
  if (viewName === "plan") refreshPlan();
  if (viewName === "account") refreshAccount();
  if (viewName === "report") refreshReport();
  if (viewName === "alert-history") refreshAlertHistory();
  if (viewName === "settings") refreshSettings();
}

async function refreshDashboard() {
  const [
    latest,
    series,
    logs,
    alerts,
    adherence,
    goals,
    gainQuality,
    energyBalance,
    incrementAnalytics,
  ] = await Promise.all([
    api.metricsLatest().catch(() => null),
    api.metricsSeries().catch(() => []),
    api.listLogs().catch(() => []),
    api.alerts().catch(() => []),
    api.adherence().catch(() => null),
    api.goals().catch(() => []),
    api.gainQuality().catch(() => []),
    api.energyBalance().catch(() => []),
    api.incrementAnalytics().catch(() => []),
  ]);
  state.series = series;
  renderDashboardStats(
    document.getElementById("dashboard-stats"),
    latest,
    adherence,
    gainQuality[gainQuality.length - 1],
    energyBalance[energyBalance.length - 1],
    incrementAnalytics[incrementAnalytics.length - 1]
  );
  renderAlerts(document.getElementById("dashboard-alerts"), alerts);
  renderSexDisclaimer(document.getElementById("sex-disclaimer"), state.profile);

  const logsById = new Map(logs.map((log) => [log.log_id, log]));
  const isProjected = (row) => row.source === "projected";

  drawLineChart(
    document.getElementById("chart-weight"),
    series.map((row) => ({
      date: row.date,
      value: row.fat_mass_kg + row.lean_mass_kg,
      projected: row.source === "projected",
    })),
    { label: "Weight" }
  );
  drawLineChart(
    document.getElementById("chart-bodyfat"),
    series.map((row) => ({
      date: row.date,
      value: row.body_fat * 100,
      projected: row.source === "projected",
    })),
    { label: "Body fat %" }
  );
  drawStackedBars(
    document.getElementById("chart-mass"),
    series.map((row) => ({ date: row.date, fat: row.fat_mass_kg, lean: row.lean_mass_kg }))
  );
  drawLineChart(
    document.getElementById("chart-calories"),
    series.map((row) => ({
      date: row.date,
      value: row.target_calories,
      projected: row.source === "projected",
    })),
    { label: "Target calories" }
  );
  drawMultiLineChart(
    document.getElementById("chart-perimeters"),
    series,
    [
      {
        accessor: (row) => (logsById.get(row.log_id) || {}).waist_cm || 0,
        color: "#5eb3ff",
        label: "Waist",
      },
      {
        accessor: (row) => (logsById.get(row.log_id) || {}).neck_cm || 0,
        color: "#f0b94d",
        label: "Neck",
      },
    ],
    { isProjected }
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

  const goalMarkers = goals.map((goal) => ({
    date: goal.start_date,
    label: `Plan changed: target BF ${(goal.target_bf * 100).toFixed(1)}%, rate ${(
      goal.weekly_rate * 100
    ).toFixed(2)}%/wk`,
  }));
  drawMultiLineChart(
    document.getElementById("chart-goal-trajectory"),
    series,
    [
      { accessor: (row) => row.fat_mass_kg + row.lean_mass_kg, color: "#5eb3ff", label: "Actual" },
      {
        accessor: (row) => row.weight_objective_kg,
        color: "#7ee787",
        dashed: true,
        label: "Target",
      },
    ],
    { isProjected, markers: goalMarkers }
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
}

async function refreshLogs() {
  state.logs = await api.listLogs();
  renderLogTable(document.querySelector("#log-table tbody"), state.logs);
  goToLogStep(1);
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

async function refreshProjection() {
  const weeks = Number(document.getElementById("projection-weeks").value) || 4;
  const base = document.getElementById("projection-base").value;
  const activity = document.getElementById("projection-activity").value;
  try {
    const rows = await api.projection(weeks, base, activity);
    renderProjectionTable(document.querySelector("#projection-table tbody"), rows);
  } catch (err) {
    // Not enough real logs yet to fit a trend.
    renderProjectionTable(document.querySelector("#projection-table tbody"), []);
  }
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

document.getElementById("log-next").addEventListener("click", () => {
  if (!currentLogStepIsValid()) return;
  goToLogStep(Math.min(logWizardStep + 1, LOG_WIZARD_STEPS));
});

document.getElementById("log-back").addEventListener("click", () => {
  goToLogStep(Math.max(logWizardStep - 1, 1));
});

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
  await refreshDashboard();
});

document.getElementById("report-print-btn").addEventListener("click", () => {
  window.print();
});

document.getElementById("projection-refresh").addEventListener("click", refreshProjection);

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
  };
  try {
    await api.updateSettings(payload);
    await refreshSettings();
  } catch (err) {
    setFormError("settings-form", err.message);
  }
});

boot();
