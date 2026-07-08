"""Desktop-runnable test for local_server.py (Phase 6's on-device entry
point) -- verifies it against a real socket without needing Chaquopy, an
Android device, or an emulator. Excluded from the Chaquopy-bundled APK
(see android/app/build.gradle's sourceSets exclude list): this only ever
runs on the desktop `justfitting` conda env, same as server/test.

Not discovered by `python -m unittest discover -s server/test` (a
different directory) -- run directly:
    python android/app/src/main/python/local_server_test.py
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
import urllib.request
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _THIS_DIR.parents[4]  # android/app/src/main/python -> repo root
for _path in (str(_REPO_ROOT), str(_THIS_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import local_server  # noqa: E402  (path bootstrap must run first)

PORT = 18765


class LocalServerTest(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp(prefix="justfitting_local_server_test_")
        self.db_path = os.path.join(self.tmp_dir, "justfitting.db")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_start_binds_socket_and_serves_the_real_app(self):
        returned_port = local_server.start(self.db_path, PORT)
        self.assertEqual(returned_port, PORT)

        with urllib.request.urlopen(
            f"http://127.0.0.1:{PORT}/api/health", timeout=5
        ) as response:
            body = json.loads(response.read())
        self.assertEqual(body, {"status": "ok"})

        # DB.__init__ connects (creating the file) and applies the schema
        # eagerly -- proves DB_PATH was actually threaded through to the
        # app factory, not just that *some* server answered on the port.
        self.assertTrue(os.path.exists(self.db_path))

        # Idempotent: a second call (Android re-running onCreate() on a
        # config change) must not error or rebind, and must still serve.
        second_port = local_server.start(self.db_path, PORT)
        self.assertEqual(second_port, PORT)
        with urllib.request.urlopen(
            f"http://127.0.0.1:{PORT}/api/health", timeout=5
        ) as response:
            body = json.loads(response.read())
        self.assertEqual(body, {"status": "ok"})


if __name__ == "__main__":
    unittest.main()
