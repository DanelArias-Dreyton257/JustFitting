"""Prod WSGI entry point: ``waitress-serve --call server.wsgi:create_app``
or ``gunicorn server.wsgi:app`` (see render.yaml), run from the repo root.

No ``load_dotenv()`` here on purpose: production entry points get real
environment variables from the platform (Render, etc.), never a `.env`
file — that's only read by the dev entry points (`Server.py`/`Client.py`).
"""

from __future__ import annotations

from server.src.api.app import create_app

app = create_app()
