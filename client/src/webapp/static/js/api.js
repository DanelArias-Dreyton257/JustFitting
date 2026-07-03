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

  listLogs: () => request("GET", "/api/logs"),
  createLog: (payload) => request("POST", "/api/logs", { body: payload }),
  updateLog: (logId, payload) => request("PUT", `/api/logs/${logId}`, { body: payload }),
  deleteLog: (logId) => request("DELETE", `/api/logs/${logId}`),

  metricsLatest: () => request("GET", "/api/metrics/latest"),
  metricsSeries: () => request("GET", "/api/metrics/series"),
  adherence: () => request("GET", "/api/metrics/adherence"),
  alerts: (includeAcknowledged = false) =>
    request("GET", `/api/alerts?include_acknowledged=${includeAcknowledged}`),
  acknowledgeAlert: (alertId) => request("POST", `/api/alerts/${alertId}/acknowledge`),

  projection: (weeks, base, activity = "constant") =>
    request("GET", `/api/projection?weeks=${weeks}&base=${base}&activity=${activity}`),

  planPreview: (params) =>
    request("GET", `/api/plan/preview?${new URLSearchParams(params).toString()}`),

  goals: () => request("GET", "/api/users/me/goals"),
  report: () => request("GET", "/api/users/me/report"),

  getSettings: () => request("GET", "/api/users/me/settings"),
  updateSettings: (payload) => request("PUT", "/api/users/me/settings", { body: payload }),
  settingsHistory: () => request("GET", "/api/users/me/settings/history"),
};
