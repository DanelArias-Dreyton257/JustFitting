"""Flask entry point serving the static web client (port 5500).

Also exposed as ``client_bp`` so ``server/src/api/app.py`` can mount it
directly when ``JUSTFITTING_SERVE_CLIENT=true`` (Phase 2 Android wrapper:
one process answering both the API and the page).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from flask import Blueprint, Flask, render_template

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
