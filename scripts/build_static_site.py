#!/usr/bin/env python3
"""Build the web client into dist/ for a static host like GitHub Pages.

The client is normally served by Flask (client/src/Client.py), which
renders index.html through Jinja to inject JUSTFITTING_API_BASE_URL. This
script performs the same substitution once, ahead of time, so the result
is plain static HTML/CSS/JS with no server required.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEBAPP_DIR = ROOT / "client" / "src" / "webapp"
DIST_DIR = ROOT / "dist"


def build(api_base_url: str) -> None:
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    DIST_DIR.mkdir(parents=True)

    shutil.copytree(WEBAPP_DIR / "static", DIST_DIR / "static")

    template = (WEBAPP_DIR / "templates" / "index.html").read_text(encoding="utf-8")
    html = (
        template.replace("{{ api_base_url }}", api_base_url)
        .replace(
            "{{ url_for('client.static', filename='css/style.css') }}",
            "static/css/style.css",
        )
        .replace(
            "{{ url_for('client.static', filename='js/app.js') }}", "static/js/app.js"
        )
    )
    (DIST_DIR / "index.html").write_text(html, encoding="utf-8")
    print(f"Built static client into {DIST_DIR} (API base: {api_base_url})")


if __name__ == "__main__":
    base_url = (
        sys.argv[1]
        if len(sys.argv) > 1
        else os.environ.get("JUSTFITTING_API_BASE_URL", "http://127.0.0.1:5000")
    )
    build(base_url)
