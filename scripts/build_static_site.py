#!/usr/bin/env python3
"""Build the web client into dist/ for a static host like GitHub Pages.

The client is normally served by Flask (client/src/Client.py), which
renders index.html through Jinja to inject JUSTFITTING_API_BASE_URL and
resolve url_for(...) calls. This script performs the same substitution
once, ahead of time, so the result is plain static HTML/CSS/JS with no
server required -- and copies manifest.json/sw.js to the site root, since
a static host has no routes to serve them there dynamically (see
client/src/Client.py's manifest()/service_worker() routes, and the
"Android app" section of README.md for why they need to live at the
root, not under static/).
"""

from __future__ import annotations

import os
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEBAPP_DIR = ROOT / "client" / "src" / "webapp"
DIST_DIR = ROOT / "dist"

# Matches {{ url_for('client.static', filename='...') }} -> static/...
_STATIC_URL_FOR_RE = re.compile(
    r"""\{\{\s*url_for\(\s*['"]client\.static['"]\s*,\s*filename=['"]([^'"]+)['"]\s*\)\s*\}\}"""
)


def _resolve_url_for(template: str) -> str:
    html = _STATIC_URL_FOR_RE.sub(lambda match: f"static/{match.group(1)}", template)
    html = html.replace("{{ url_for('client.manifest') }}", "manifest.json")
    html = html.replace("{{ url_for('client.service_worker') }}", "sw.js")
    return html


def build(api_base_url: str) -> None:
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    DIST_DIR.mkdir(parents=True)

    shutil.copytree(WEBAPP_DIR / "static", DIST_DIR / "static")
    shutil.copy(WEBAPP_DIR / "static" / "manifest.json", DIST_DIR / "manifest.json")
    shutil.copy(WEBAPP_DIR / "static" / "sw.js", DIST_DIR / "sw.js")

    template = (WEBAPP_DIR / "templates" / "index.html").read_text(encoding="utf-8")
    html = _resolve_url_for(template).replace("{{ api_base_url }}", api_base_url)
    (DIST_DIR / "index.html").write_text(html, encoding="utf-8")
    print(f"Built static client into {DIST_DIR} (API base: {api_base_url})")


if __name__ == "__main__":
    base_url = (
        sys.argv[1]
        if len(sys.argv) > 1
        else os.environ.get("JUSTFITTING_API_BASE_URL", "http://127.0.0.1:5000")
    )
    build(base_url)
