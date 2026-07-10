package com.danelarias.justfitting;

import com.getcapacitor.JSArray;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

import java.time.LocalDate;
import java.time.format.DateTimeParseException;
import java.util.Arrays;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Phase 7.3 (Health Connect bridge, see README): reads Steps (Mi Fitness)
 * and Nutrition (Samsung Health) data those apps already sync into Android
 * Health Connect on-device -- this app never talks to either app's own
 * servers/SDKs directly, only to Health Connect. Read-only, manual-sync-only
 * (a "Sync now" button, no background job -- see README's Phase 7.3/7.4
 * "manual sync only, for now"), Android app only.
 *
 * The actual connect-client API calls live in HealthConnectBridge.kt, the
 * one Kotlin file in this app -- its suspend-function-based API needs a
 * Kotlin caller (see that file's own doc comment for why). This class is
 * the ordinary Capacitor plugin surface client/src/webapp/static/js/
 * healthSync.js talks to; it never references connect-client types
 * directly, only HealthConnectBridge's plain Java-callable wrappers.
 */
@CapacitorPlugin(name = "HealthSync")
public class HealthSyncPlugin extends Plugin {

    // README's Phase 7.3 "Open risks": Mi Fitness's Health-Connect-visible
    // package name has varied by region/firmware, so this is a small
    // known-alias list, not one hardcoded string -- confirming/expanding
    // this list against a real device is exactly the kind of thing this
    // phase's on-device verification step is for.
    private static final Set<String> MI_FITNESS_PACKAGES = new HashSet<>(
        Arrays.asList("com.xiaomi.wearable", "com.mi.health", "com.xiaomi.hm.health")
    );
    private static final Set<String> SAMSUNG_HEALTH_PACKAGES = new HashSet<>(
        Arrays.asList("com.sec.android.app.shealth")
    );

    // Health Connect calls block (HealthConnectBridge.kt's runBlocking) --
    // dispatched off Capacitor's own call-handling thread explicitly,
    // rather than relying on it already not being the main thread, to
    // match this project's "explicit, not implicit" convention elsewhere
    // (see app/build.gradle's compileOptions comment).
    private final ExecutorService executor = Executors.newSingleThreadExecutor();

    @PluginMethod
    public void isAvailable(PluginCall call) {
        executor.execute(() -> {
            int status = HealthConnectBridge.sdkStatus(getContext());
            String statusName;
            if (status == HealthConnectBridge.SDK_AVAILABLE) {
                statusName = "available";
            } else if (status == HealthConnectBridge.SDK_UNAVAILABLE_PROVIDER_UPDATE_REQUIRED) {
                statusName = "update_required";
            } else {
                statusName = "not_installed";
            }
            JSObject ret = new JSObject();
            ret.put("available", status == HealthConnectBridge.SDK_AVAILABLE);
            ret.put("status", statusName);
            call.resolve(ret);
        });
    }

    // Phase 7.5 (Settings UI, see README): reports Steps/Nutrition
    // separately, not just one combined boolean -- Health Connect's own
    // permission dialog lets the user grant one and deny the other.
    @PluginMethod
    public void hasPermissions(PluginCall call) {
        executor.execute(() -> {
            Set<String> granted = HealthConnectBridge.grantedPermissions(getContext());
            boolean steps = granted.contains(HealthConnectBridge.STEPS_PERMISSION);
            boolean nutrition = granted.contains(HealthConnectBridge.NUTRITION_PERMISSION);
            JSObject ret = new JSObject();
            ret.put("steps", steps);
            ret.put("nutrition", nutrition);
            ret.put("granted", steps && nutrition);
            call.resolve(ret);
        });
    }

    // Must run on the main thread (launches an Activity Result contract) --
    // MainActivity owns the registered ActivityResultLauncher, since
    // registerForActivityResult() has to be called during onCreate(), long
    // before any plugin call could exist. See MainActivity.java.
    @PluginMethod
    public void requestPermissions(PluginCall call) {
        MainActivity activity = (MainActivity) getActivity();
        if (activity == null) {
            call.reject("No activity available");
            return;
        }
        activity.requestHealthPermissions(HealthConnectBridge.allPermissions(), grantedPermissions -> {
            JSObject ret = new JSObject();
            ret.put("granted", grantedPermissions.containsAll(HealthConnectBridge.allPermissions()));
            call.resolve(ret);
        });
    }

    @PluginMethod
    public void readRecentReadings(PluginCall call) {
        String sinceDateStr = call.getString("sinceDate");
        if (sinceDateStr == null) {
            call.reject("sinceDate is required");
            return;
        }
        LocalDate sinceDate;
        try {
            sinceDate = LocalDate.parse(sinceDateStr);
        } catch (DateTimeParseException e) {
            call.reject("sinceDate must be an ISO date (YYYY-MM-DD)");
            return;
        }

        executor.execute(() -> {
            try {
                if (!HealthConnectBridge.hasAllPermissions(getContext(), HealthConnectBridge.requiredPermissions())) {
                    call.reject("Health Connect permissions not granted");
                    return;
                }
                // untilDate is always computed natively here as tomorrow --
                // never trusted from the JS caller -- so today itself is
                // included as the range's last (partial) day. Phase 7.3
                // originally excluded today entirely (today's count is still
                // accumulating mid-day, "the 'not today' rule"), but Phase
                // 10.2's Today dashboard section now exists specifically to
                // show a still-accumulating same-day reading, flagged as
                // current/incomplete -- so a synced today reading is no
                // longer a shortfall read with nowhere sensible to land, and
                // withholding it just delayed the Today section by one sync.
                // A day's true final total still arrives automatically: the
                // next sync run on a *later* calendar day re-reads and
                // upserts (never duplicates, README's Phase 7.4/7.5) that
                // now-past day with its now-complete aggregate, overwriting
                // whatever partial number was captured while it was "today."
                LocalDate today = LocalDate.now();
                List<DailyReading> readings = HealthConnectBridge.readDailyReadings(
                    getContext(), sinceDate, today.plusDays(1), MI_FITNESS_PACKAGES, SAMSUNG_HEALTH_PACKAGES
                );
                JSArray array = new JSArray();
                for (DailyReading reading : readings) {
                    array.put(toJson(reading));
                }
                JSObject ret = new JSObject();
                ret.put("readings", array);
                call.resolve(ret);
            } catch (Exception e) {
                call.reject("Health Connect read failed: " + e.getMessage(), e);
            }
        });
    }

    private JSObject toJson(DailyReading reading) {
        JSObject json = new JSObject();
        json.put("date", reading.getDate());
        if (reading.getSteps() != null) json.put("steps", reading.getSteps());
        if (reading.getIntakeKcal() != null) json.put("intake_kcal", reading.getIntakeKcal());
        if (reading.getCarbsG() != null) json.put("carbs_g", reading.getCarbsG());
        if (reading.getFatG() != null) json.put("fat_g", reading.getFatG());
        if (reading.getProteinG() != null) json.put("protein_g", reading.getProteinG());
        return json;
    }
}
