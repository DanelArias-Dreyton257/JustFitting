"""A tiny Flask app serving the real client static JS plus minimal
test-harness pages, used only by the Playwright browser tests in this
directory. Never shipped, never registered by the real client/server apps
-- it just points Flask's static folder at the real
`client/src/webapp/static/js/{views,api,session}.js` so tests exercise the
actual shipped code, not a copy.
"""

from __future__ import annotations

from pathlib import Path

from flask import Flask, render_template

WEBAPP_STATIC_DIR = Path(__file__).resolve().parents[2] / "src" / "webapp" / "static"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def create_harness_app(api_base_url: str = "") -> Flask:
    app = Flask(
        __name__,
        static_folder=str(WEBAPP_STATIC_DIR),
        static_url_path="/static",
        template_folder=str(FIXTURES_DIR),
    )

    @app.get("/harness/views")
    def views_harness():
        return render_template("views_harness.html")

    @app.get("/harness/api")
    def api_harness():
        return render_template("api_harness.html", api_base_url=api_base_url)

    return app
