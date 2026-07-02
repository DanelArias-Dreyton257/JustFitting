"""Dev entry point: ``python -m server.src.Server`` (run from repo root).

Pure-Flask dev server on purpose (no gunicorn on this path); prod uses
``server/wsgi.py`` instead (see README's Deployment section).
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

from server.src.api.app import create_app  # noqa: E402  (import after load_dotenv)


def resolve_server_config() -> tuple[str, int, bool]:
    host = os.environ.get("JUSTFITTING_SERVER_HOST", "127.0.0.1")
    port = int(os.environ.get("JUSTFITTING_SERVER_PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    return host, port, debug


def main() -> None:
    app = create_app()
    host, port, debug = resolve_server_config()
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    main()
