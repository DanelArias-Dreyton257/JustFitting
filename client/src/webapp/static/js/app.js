// Controller: holds all app state, wires DOM events to api.js and views.js.
import { api } from "./api.js";
import { getToken, setToken, clearToken, isAuthenticated } from "./session.js";
import {
  showView,
  setFormError,
  renderDashboardStats,
  renderAlerts,
  renderLogTable,
  renderProjectionTable,
  fillProfileForm,
  showWizardStep,
  renderLogReview,
  renderPlanStats,
} from "./views.js";
import { drawLineChart, drawStackedBars, drawMultiLineChart } from "./charts.js";

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
}

async function refreshDashboard() {
  const [latest, series, logs, alerts] = await Promise.all([
    api.metricsLatest().catch(() => null),
    api.metricsSeries().catch(() => []),
    api.listLogs().catch(() => []),
    api.alerts().catch(() => []),
  ]);
  state.series = series;
  renderDashboardStats(document.getElementById("dashboard-stats"), latest);
  renderAlerts(document.getElementById("dashboard-alerts"), alerts);

  const logsById = new Map(logs.map((log) => [log.log_id, log]));
  const isProjected = (row) => row.source === "projected";

  drawLineChart(
    document.getElementById("chart-weight"),
    series.map((row) => ({
      value: row.fat_mass_kg + row.lean_mass_kg,
      projected: row.source === "projected",
    }))
  );
  drawLineChart(
    document.getElementById("chart-bodyfat"),
    series.map((row) => ({ value: row.body_fat * 100, projected: row.source === "projected" }))
  );
  drawStackedBars(
    document.getElementById("chart-mass"),
    series.map((row) => ({ fat: row.fat_mass_kg, lean: row.lean_mass_kg }))
  );
  drawLineChart(
    document.getElementById("chart-calories"),
    series.map((row) => ({ value: row.target_calories, projected: row.source === "projected" }))
  );
  drawMultiLineChart(
    document.getElementById("chart-perimeters"),
    series,
    [
      { accessor: (row) => (logsById.get(row.log_id) || {}).waist_cm || 0, color: "#5eb3ff" },
      { accessor: (row) => (logsById.get(row.log_id) || {}).neck_cm || 0, color: "#f0b94d" },
    ],
    { isProjected }
  );
  drawLineChart(
    document.getElementById("chart-steps"),
    series.map((row) => ({
      value: (logsById.get(row.log_id) || {}).steps || 0,
      projected: row.source === "projected",
    }))
  );
  drawMultiLineChart(
    document.getElementById("chart-goal-trajectory"),
    series,
    [
      { accessor: (row) => row.fat_mass_kg + row.lean_mass_kg, color: "#5eb3ff" },
      { accessor: (row) => row.weight_objective_kg, color: "#7ee787", dashed: true },
    ],
    { isProjected }
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
  const [profile, current] = await Promise.all([
    api.me(),
    api.metricsLatest().catch(() => null),
  ]);
  state.profile = profile;
  const form = document.getElementById("plan-form");
  form.target_bf_pct.value = (profile.target_bf * 100).toFixed(1);
  form.weekly_rate_pct.value = (profile.weekly_rate * 100).toFixed(2);
  renderPlanStats(document.getElementById("plan-current-stats"), current);
  state.planPreviewParams = null;
  document.getElementById("plan-preview-result").hidden = true;
  setFormError("plan-form", "");
  setFormError("plan-commit", "");
}

async function refreshProjection() {
  const weeks = Number(document.getElementById("projection-weeks").value) || 4;
  const base = document.getElementById("projection-base").value;
  try {
    const rows = await api.projection(weeks, base);
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
    renderPlanStats(document.getElementById("plan-proposed-stats"), proposed);
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

boot();
