const STORAGE_KEY = "justfitting.token";

export function getToken() {
  return localStorage.getItem(STORAGE_KEY);
}

export function setToken(token) {
  localStorage.setItem(STORAGE_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(STORAGE_KEY);
}

export function isAuthenticated() {
  return Boolean(getToken());
}

// Phase 4.5: a pure display preference (not an engine input), so it lives in
// localStorage rather than the server-persisted, historized EngineSettings
// -- no account sync, no migration, just a per-browser toggle. Defaults on
// (unset key -> true) so a first-time user sees projected rows without
// having to find the Settings checkbox first; an explicit "false" (once the
// user turns it off) is honored from then on.
const SHOW_PROJECTED_LOGS_KEY = "justfitting.showProjectedLogs";

export function getShowProjectedLogs() {
  const stored = localStorage.getItem(SHOW_PROJECTED_LOGS_KEY);
  return stored === null ? true : stored === "true";
}

export function setShowProjectedLogs(value) {
  localStorage.setItem(SHOW_PROJECTED_LOGS_KEY, String(Boolean(value)));
}
