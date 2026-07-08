package com.danelarias.justfitting;

import android.os.Bundle;
import com.chaquo.python.PyObject;
import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;
import com.getcapacitor.BridgeActivity;
import java.io.File;

/**
 * Phase 6 (embedded on-device server, see README's "Android app ->
 * Embedded on-device server" section): starts the same Flask API
 * server/src/api/app.py builds for the desktop/Render deployments,
 * running in-process via Chaquopy, before the WebView is created --
 * android/app/src/main/python/local_server.py's start() only returns
 * once its socket is actually bound, so the client's first fetch never
 * races an unbound port.
 */
public class MainActivity extends BridgeActivity {
    // Loopback-only; matches the port scripts/build_static_site.py's
    // embedded-server target bakes into JUSTFITTING_API_BASE_URL.
    private static final int LOCAL_SERVER_PORT = 5000;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        startLocalServer();
        super.onCreate(savedInstanceState);
    }

    private void startLocalServer() {
        if (!Python.isStarted()) {
            Python.start(new AndroidPlatform(this));
        }
        Python python = Python.getInstance();
        PyObject localServer = python.getModule("local_server");
        String dbPath = new File(getFilesDir(), "justfitting.db").getAbsolutePath();
        localServer.callAttr("start", dbPath, LOCAL_SERVER_PORT);
    }
}
