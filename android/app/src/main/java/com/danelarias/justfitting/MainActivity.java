package com.danelarias.justfitting;

import android.os.Bundle;
import androidx.core.splashscreen.SplashScreen;
import com.chaquo.python.PyObject;
import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;
import com.getcapacitor.BridgeActivity;
import java.io.File;
import java.util.concurrent.atomic.AtomicBoolean;

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
 */
public class MainActivity extends BridgeActivity {
    // Loopback-only; matches the port scripts/build_static_site.py's
    // embedded-server target bakes into JUSTFITTING_API_BASE_URL.
    private static final int LOCAL_SERVER_PORT = 5000;

    private final AtomicBoolean localServerReady = new AtomicBoolean(false);

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        SplashScreen splashScreen = SplashScreen.installSplashScreen(this);
        splashScreen.setKeepOnScreenCondition(() -> !localServerReady.get());
        startLocalServerAsync();
        super.onCreate(savedInstanceState);
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
