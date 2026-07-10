// The only module that talks to the network. Every other module imports
// `api` instead of calling fetch() directly.
import { getToken } from "./session.js";

const BASE_URL = window.JUSTFITTING_API_BASE_URL || "http://127.0.0.1:5000";

export class ApiError extends Error {
  constructor(status, payload) {
    super((payload && payload.error) || `Request failed with status ${status}`);
    this.status = status;
    this.payload = payload;
  }
}

async function request(method, path, { body, auth = true } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (auth) {
    const token = getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }
  const response = await fetch(`${BASE_URL}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (response.status === 204) return null;
  const payload = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(response.status, payload);
  return payload;
}

export const api = {
  register: (payload) => request("POST", "/api/users", { body: payload, auth: false }),
  login: (payload) => request("POST", "/api/auth/login", { body: payload, auth: false }),
  logout: () => request("POST", "/api/auth/logout"),
  resetPassword: (identifier, newPassword) =>
    request("POST", "/api/auth/reset-password", {
      body: { identifier, new_password: newPassword },
      auth: false,
    }),
  me: () => request("GET", "/api/users/me"),
  updateProfile: (payload) => request("PUT", "/api/users/me", { body: payload }),
  changePassword: (payload) => request("POST", "/api/users/me/password", { body: payload }),
  deleteAccount: () => request("DELETE", "/api/users/me"),
  exportData: () => request("GET", "/api/users/me/export"),
  importData: (payload) => request("POST", "/api/users/me/import", { body: payload }),

  // Phase 9.1/9.2 (body composition logging separation, see README):
  // sporadic waist/neck (plus, since Phase 9.3, nine more record-only
  // perimeters) -- deliberately separate from /api/logs.
  listBodyMeasurements: () => request("GET", "/api/body-measurements"),
  saveBodyMeasurement: (payload) => request("POST", "/api/body-measurements", { body: payload }),
  updateBodyMeasurement: (measurementId, payload) =>
    request("PUT", `/api/body-measurements/${measurementId}`, { body: payload }),
  deleteBodyMeasurement: (measurementId) =>
    request("DELETE", `/api/body-measurements/${measurementId}`),

  listLogs: () => request("GET", "/api/logs"),
  createLog: (payload) => request("POST", "/api/logs", { body: payload }),
  updateLog: (logId, payload) => request("PUT", `/api/logs/${logId}`, { body: payload }),
  deleteLog: (logId) => request("DELETE", `/api/logs/${logId}`),
  // Phase 7.4/7.5 (partial logs & Health Connect sync, see README):
  // order-/source-independent merge for one date -- only touches the
  // given fields, creating a partial row if none exists yet.
  upsertLogByDate: (date, fields) =>
    request("PUT", `/api/logs/by-date/${date}`, { body: fields }),

  metricsLatest: () => request("GET", "/api/metrics/latest"),
  metricsSeries: () => request("GET", "/api/metrics/series"),
  adherence: () => request("GET", "/api/metrics/adherence"),
  gainQuality: () => request("GET", "/api/metrics/gain-quality"),
  energyBalance: () => request("GET", "/api/metrics/energy-balance"),
  incrementAnalytics: () => request("GET", "/api/metrics/increment-analytics"),
  tef: () => request("GET", "/api/metrics/tef"),
  macroTargets: () => request("GET", "/api/metrics/macro-targets"),
  alerts: (includeAcknowledged = false) =>
    request("GET", `/api/alerts?include_acknowledged=${includeAcknowledged}`),
  acknowledgeAlert: (alertId) => request("POST", `/api/alerts/${alertId}/acknowledge`),

  projection: (weeks, base, activity = "constant") =>
    request("GET", `/api/projection?weeks=${weeks}&base=${base}&activity=${activity}`),

  planPreview: (params) =>
    request("GET", `/api/plan/preview?${new URLSearchParams(params).toString()}`),

  goals: () => request("GET", "/api/users/me/goals"),
  // Phase 8.1: corrects the active goal's own start_date in place, not a
  // new historized row.
  updateGoalStartDate: (startDate) =>
    request("PUT", "/api/users/me/goals/active/start-date", {
      body: { start_date: startDate },
    }),
  report: () => request("GET", "/api/users/me/report"),

  getSettings: () => request("GET", "/api/users/me/settings"),
  updateSettings: (payload) => request("PUT", "/api/users/me/settings", { body: payload }),
  settingsHistory: () => request("GET", "/api/users/me/settings/history"),
};
