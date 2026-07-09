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

// {steps: boolean, nutrition: boolean, granted: boolean} -- steps/nutrition
// report each source independently (Health Connect's own permission
// dialog lets the user grant one and deny the other); granted is both.
export async function hasPermissions() {
  const plugin = nativePlugin();
  if (!plugin) return { steps: false, nutrition: false, granted: false };
  return plugin.hasPermissions();
}

// {granted: boolean} -- triggers Health Connect's own system permission UI.
export async function requestPermissions() {
  const plugin = nativePlugin();
  if (!plugin) return { granted: false };
  return plugin.requestPermissions();
}

// Health Connect's aggregate readers return raw floating-point sums (e.g.
// carbs_g: 210.00000000000003 -- a sum-of-grams float artifact, not a
// meaningful extra 13 decimal places of precision). Rounded here, at the
// boundary where a native reading enters the JS layer, so every caller
// (today just app.js's "Sync now" handler) stores a clean value rather
// than each having to remember to round before persisting.
function roundToOneDecimal(value) {
  return value == null ? value : Math.round(value * 10) / 10;
}

// Only rounds fields actually present -- mirrors HealthSyncPlugin.java's
// own toJson, which omits a field entirely rather than sending it null.
function roundReading(reading) {
  const rounded = { ...reading };
  for (const field of ["steps", "intake_kcal", "carbs_g", "fat_g", "protein_g"]) {
    if (rounded[field] != null) rounded[field] = roundToOneDecimal(rounded[field]);
  }
  return rounded;
}

// {readings: [{date, steps?, intake_kcal?, carbs_g?, fat_g?, protein_g?}]}
// sinceDate is an ISO "YYYY-MM-DD" string; the native side always excludes
// today itself (the "not today" rule -- README's Phase 7.3), regardless of
// what's passed here.
export async function syncRecentReadings(sinceDate) {
  const plugin = nativePlugin();
  if (!plugin) return { readings: [] };
  const { readings } = await plugin.readRecentReadings({ sinceDate });
  return { readings: readings.map(roundReading) };
}
