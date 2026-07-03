"""Runs a Flask app on a background thread so Playwright can navigate a real
browser to it -- these tests boot the real client/server apps, no mocking.
"""

from __future__ import annotations

import threading

from werkzeug.serving import make_server


class LiveServer:
    def __init__(self, app, host: str = "127.0.0.1"):
        self._server = make_server(host, 0, app)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self._server.server_port}"

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._server.shutdown()
        self._thread.join(timeout=5)
