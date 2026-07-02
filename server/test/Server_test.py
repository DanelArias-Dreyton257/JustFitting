import os
import unittest

from server.src.Server import resolve_server_config


class ServerConfigTest(unittest.TestCase):
    def setUp(self):
        self._saved = {
            key: os.environ.get(key)
            for key in (
                "JUSTFITTING_SERVER_HOST",
                "JUSTFITTING_SERVER_PORT",
                "FLASK_DEBUG",
            )
        }

    def tearDown(self):
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_defaults(self):
        for key in self._saved:
            os.environ.pop(key, None)
        host, port, debug = resolve_server_config()
        self.assertEqual(host, "127.0.0.1")
        self.assertEqual(port, 5000)
        self.assertFalse(debug)

    def test_reads_env_overrides(self):
        os.environ["JUSTFITTING_SERVER_HOST"] = "0.0.0.0"
        os.environ["JUSTFITTING_SERVER_PORT"] = "8080"
        os.environ["FLASK_DEBUG"] = "true"
        host, port, debug = resolve_server_config()
        self.assertEqual(host, "0.0.0.0")
        self.assertEqual(port, 8080)
        self.assertTrue(debug)


if __name__ == "__main__":
    unittest.main()
