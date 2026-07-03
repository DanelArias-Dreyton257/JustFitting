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

    def test_manifest_is_served_at_root_with_correct_mimetype(self):
        response = self.client.get("/manifest.json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/manifest+json")
        payload = response.get_json()
        self.assertEqual(payload["name"], "JustFitting")
        self.assertEqual(payload["start_url"], "/")

    def test_service_worker_is_served_at_root_with_full_scope(self):
        response = self.client.get("/sw.js")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "text/javascript")
        self.assertEqual(response.headers.get("Service-Worker-Allowed"), "/")

    def test_index_references_manifest_and_service_worker(self):
        response = self.client.get("/")
        self.assertIn(b'rel="manifest"', response.data)
        self.assertIn(b"serviceWorker", response.data)

    def test_icons_are_served(self):
        for filename in ("icon-192.png", "icon-512.png", "favicon-32.png"):
            response = self.client.get(f"/static/icons/{filename}")
            self.assertEqual(response.status_code, 200, f"{filename} was not served")

    def test_index_includes_phase_1_5_nav_and_views(self):
        response = self.client.get("/")
        for nav_view in (b'data-view="alert-history"', b'data-view="settings"'):
            self.assertIn(nav_view, response.data)
        for section_id in (b'id="view-alert-history"', b'id="view-settings"'):
            self.assertIn(section_id, response.data)
        self.assertIn(b'id="reset-password-form"', response.data)
        self.assertIn(b'id="sex-disclaimer"', response.data)
        self.assertIn(b'id="projection-activity"', response.data)


if __name__ == "__main__":
    unittest.main()
