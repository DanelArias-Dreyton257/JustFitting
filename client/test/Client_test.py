import unittest

from client.src.Client import create_client_app


class ClientSmokeTest(unittest.TestCase):
    def setUp(self):
        self.app = create_client_app({"TESTING": True})
        self.client = self.app.test_client()

    def test_index_is_served(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"JustFitting", response.data)
        self.assertIn(b"window.JUSTFITTING_API_BASE_URL", response.data)

    def test_static_js_modules_are_served(self):
        for filename in ("api.js", "session.js", "views.js", "app.js", "charts.js"):
            response = self.client.get(f"/static/js/{filename}")
            self.assertEqual(response.status_code, 200, f"{filename} was not served")

    def test_static_css_is_served(self):
        response = self.client.get("/static/css/style.css")
        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
