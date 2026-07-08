"""On-device entry point for Phase 6's embedded server (see README's
"Android app -> Embedded on-device server" section).

Called from Kotlin/Java (``MainActivity.onCreate``, before ``super
.onCreate()``) via Chaquopy's Python bridge -- not a route or CLI, this
module has exactly one job: start the same Flask app
``server/src/api/app.py`` builds for the desktop/Render deployments,
served by waitress (matching ``server/wsgi.py``'s production path, never
Flask's own dev server) and bound to loopback only.

``start()`` returns as soon as the listening socket is actually bound
(``waitress.create_server`` binds synchronously; only the accept loop
itself runs on a background thread), so the caller has a real readiness
signal instead of a fixed sleep -- see ``local_server_test.py``, which
exercises this against a real socket.
"""

from __future__ import annotations

import os
import threading
from typing import Optional

import waitress

from server.src.api.app import create_app

_server: Optional["waitress.server.BaseWSGIServer"] = None
_lock = threading.Lock()


def start(db_path: str, port: int) -> int:
    """Idempotent: Android can re-run ``onCreate()`` (e.g. a config
    change) without killing the process, so a second call with the
    server already running is a no-op that just returns the same port.
    """
    global _server
    with _lock:
        if _server is not None:
            return port

        os.environ["JUSTFITTING_DB_PATH"] = db_path
        os.environ.setdefault("JUSTFITTING_CORS_ORIGINS", "https://localhost")

        app = create_app()
        _server = waitress.create_server(app, host="127.0.0.1", port=port)

        thread = threading.Thread(target=_server.run, daemon=True)
        thread.start()
        return port
