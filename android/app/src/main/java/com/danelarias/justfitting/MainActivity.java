package com.danelarias.justfitting;

import android.os.Bundle;
import androidx.activity.result.ActivityResultLauncher;
import androidx.core.splashscreen.SplashScreen;
import com.chaquo.python.PyObject;
import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;
import com.getcapacitor.BridgeActivity;
import java.io.File;
import java.util.Set;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.function.Consumer;

/**
 * Phase 6 (embedded on-device server, see README's "Android app ->
 * Embedded on-device server" section): starts the same Flask API
 * server/src/api/app.py builds for the desktop/Render deployments,
 * running in-process via Chaquopy, on a background thread --
 * android/app/src/main/python/local_server.py's start() only returns
 * once its socket is actually bound. The platform splash screen
 * (res/values/styles.xml's AppTheme.NoActionBarLaunch, already
 * Theme.SplashScreen-based -- Capacitor's own scaffold, previously
 * unused) is held on screen via setKeepOnScreenCondition until that
 * background thread signals ready, instead of blocking onCreate()
 * itself: blocking risks an ANR on a slow device and gives the
 * platform's own splash-dismiss timing nothing to actually wait for.
 *
 * Also registers HealthSyncPlugin (Phase 7.3, README's "Data
 * portability & phone health-app sync" section) and owns the Health
 * Connect permission-request ActivityResultLauncher -- it has to be
 * registered here, during onCreate(), since
 * registerForActivityResult() requires that; HealthSyncPlugin calls
 * back into requestHealthPermissions() below rather than registering
 * its own launcher.
 */
public class MainActivity extends BridgeActivity {
    // Loopback-only; matches the port scripts/build_static_site.py's
    // embedded-server target bakes into JUSTFITTING_API_BASE_URL.
    private static final int LOCAL_SERVER_PORT = 5000;

    private final AtomicBoolean localServerReady = new AtomicBoolean(false);

    private ActivityResultLauncher<Set<String>> healthPermissionLauncher;
    private Consumer<Set<String>> pendingHealthPermissionCallback;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        registerPlugin(HealthSyncPlugin.class);
        SplashScreen splashScreen = SplashScreen.installSplashScreen(this);
        splashScreen.setKeepOnScreenCondition(() -> !localServerReady.get());
        startLocalServerAsync();
        super.onCreate(savedInstanceState);

        healthPermissionLauncher = registerForActivityResult(
                HealthConnectBridge.createPermissionRequestContract(),
                grantedPermissions -> {
                    if (pendingHealthPermissionCallback != null) {
                        pendingHealthPermissionCallback.accept(grantedPermissions);
                        pendingHealthPermissionCallback = null;
                    }
                });
    }

    // Called by HealthSyncPlugin.requestPermissions() -- launches Health
    // Connect's own system permission UI and reports back which of the
    // requested permissions were actually granted (the user can grant a
    // subset, e.g. Steps but not Nutrition).
    public void requestHealthPermissions(Set<String> permissions, Consumer<Set<String>> callback) {
        pendingHealthPermissionCallback = callback;
        healthPermissionLauncher.launch(permissions);
    }

    // Runs on a background thread so onCreate() returns immediately --
    // the WebView starts loading the bundled dist/index.html shell right
    // away (fully local, no network needed for that part), while the
    // splash screen above stays up until the server itself is actually
    // ready to answer requests.
    private void startLocalServerAsync() {
        new Thread(
                () -> {
                    if (!Python.isStarted()) {
                        Python.start(new AndroidPlatform(this));
                    }
                    Python python = Python.getInstance();
                    PyObject localServer = python.getModule("local_server");
                    String dbPath = new File(getFilesDir(), "justfitting.db").getAbsolutePath();
                    localServer.callAttr("start", dbPath, LOCAL_SERVER_PORT);
                    localServerReady.set(true);
                },
                "local-server-startup")
                .start();
    }
}
