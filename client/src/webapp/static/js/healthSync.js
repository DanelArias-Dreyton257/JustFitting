// Wraps the native HealthSync Capacitor plugin (Phase 7.3, README's "Data
// portability & phone health-app sync" section -- android/app/src/main/
// java/com/danelarias/justfitting/HealthSyncPlugin.java) with a graceful
// fallback for the web build and any non-Android/pre-26 device, so the rest
// of the client only ever has to feature-detect this one module instead of
// branching on platform everywhere. The identical `dist/` client is what
// both the web deployment and the Android app ship (README's Architecture
// section) -- this module is what makes that still true for a feature that
// only exists on one of them.

function nativePlugin() {
  return typeof window !== "undefined" &&
    window.Capacitor &&
    window.Capacitor.Plugins &&
    window.Capacitor.Plugins.HealthSync
    ? window.Capacitor.Plugins.HealthSync
    : null;
}

export function isSupported() {
  return nativePlugin() !== null;
}

// {available: boolean, status: "available" | "update_required" | "not_installed" | "unsupported"}
export async function checkAvailability() {
  const plugin = nativePlugin();
  if (!plugin) return { available: false, status: "unsupported" };
  return plugin.isAvailable();
}

// {granted: boolean}
export async function hasPermissions() {
  const plugin = nativePlugin();
  if (!plugin) return { granted: false };
  return plugin.hasPermissions();
}

// {granted: boolean} -- triggers Health Connect's own system permission UI.
export async function requestPermissions() {
  const plugin = nativePlugin();
  if (!plugin) return { granted: false };
  return plugin.requestPermissions();
}

// {readings: [{date, steps?, intake_kcal?, carbs_g?, fat_g?, protein_g?}]}
// sinceDate is an ISO "YYYY-MM-DD" string; the native side always excludes
// today itself (the "not today" rule -- README's Phase 7.3), regardless of
// what's passed here.
export async function syncRecentReadings(sinceDate) {
  const plugin = nativePlugin();
  if (!plugin) return { readings: [] };
  return plugin.readRecentReadings({ sinceDate });
}
