"""Flask entry point serving the static web client (port 5500)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from flask import Blueprint, Flask, render_template, send_from_directory

WEBAPP_DIR = Path(__file__).resolve().parent / "webapp"

client_bp = Blueprint(
    "client",
    __name__,
    template_folder=str(WEBAPP_DIR / "templates"),
    static_folder=str(WEBAPP_DIR / "static"),
    static_url_path="/static",
)


@client_bp.get("/")
def index():
    api_base_url = os.environ.get("JUSTFITTING_API_BASE_URL", "http://127.0.0.1:5000")
    return render_template("index.html", api_base_url=api_base_url)


@client_bp.get("/manifest.json")
def manifest():
    # Served at the root (not /static/manifest.json) so browsers can point
    # at a clean, stable https://<domain>/manifest.json for PWA installs.
    return send_from_directory(
        str(WEBAPP_DIR / "static"),
        "manifest.json",
        mimetype="application/manifest+json",
    )


@client_bp.get("/sw.js")
def service_worker():
    # A service worker's default scope is the directory it's served from,
    # so this must live at the root -- /static/js/sw.js could only ever
    # control pages under /static/js/. Service-Worker-Allowed is a
    # belt-and-suspenders confirmation of that root scope.
    response = send_from_directory(
        str(WEBAPP_DIR / "static"), "sw.js", mimetype="text/javascript"
    )
    response.headers["Service-Worker-Allowed"] = "/"
    return response


def create_client_app(config: Optional[dict] = None) -> Flask:
    app = Flask(__name__, static_folder=None)
    app.config.update(config or {})
    app.register_blueprint(client_bp)
    return app


def main() -> None:
    from dotenv import load_dotenv

    load_dotenv()
    app = create_client_app()
    host = os.environ.get("JUSTFITTING_CLIENT_HOST", "127.0.0.1")
    port = int(os.environ.get("JUSTFITTING_CLIENT_PORT", "5500"))
    app.run(host=host, port=port)


if __name__ == "__main__":
    main()
