# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Phase 1: server-client web app.
  - Composition engine (`server/src/services/composition/`) implementing
    the verified "Danel" spec — anthropometry, body-fat estimators
    (RFM/Navy/Deurenberg), energy model (BMR/NEAT/TDEE/target calories),
    goal trajectory, and OLS-based weekly projection.
  - SQLite-backed data layer with a linear migration runner, DAOs for
    users/sessions/body logs, and domain/DTO models.
  - Services layer: `UserManager` (profile CRUD, PBKDF2 password hashing),
    `AuthService` (bearer sessions with sliding expiry), `LogManager`
    (weekly log CRUD, real-vs-assumed intake, Danel reference demo seed).
  - Flask REST API: auth, profile, logs, derived metrics, and projection
    routes, plus `GET /api/health`.
  - Static, dependency-free web client (vanilla JS ES modules) with
    Dashboard, Log, Projection and Account views and hand-rolled SVG charts.
  - `scripts/` for install, run, update, reset_db, seed_demo_data and
    uninstall; `scripts/build_static_site.py` for a GitHub Pages build.
  - CI on every push/PR; a release workflow gated on CI that builds and
    publishes the client and cuts a GitHub Release on a `vX.Y.Z` tag.
- `docs/product_capabilities_spec.md` and a README roadmap (Phases 1.1–1.6)
  cross-checking the engine against the consolidated "Documento Final" v2.0
  spec and cataloguing the product capabilities (§14–§16) it defines beyond
  the calculation engine — audit trail, historized goals, alerts/feedback,
  adherence reporting, sex-specific formula variants, and more.
- PWA groundwork for the Phase 2 Android app — step 1 of the 3-step plan
  described under "Changed" below is now implemented, not just planned:
  - `client/src/webapp/static/manifest.json` (name, icons, `start_url:
    "/"`, `display: standalone`, theme/background color, `scope: "/"`).
  - An app-shell service worker (`static/sw.js`): stale-while-revalidate
    for this site's own static assets; requests to a different origin
    (the API) are left untouched.
  - Placeholder icons generated with Pillow, matching the client's dark
    theme (`static/icons/icon-192.png`, `icon-512.png`, `favicon-32.png`,
    "any" + "maskable" purposes) — meant to be swapped for real branding.
  - `Client.py` serves both `manifest.json` and `sw.js` at the site
    *root* (`GET /manifest.json`, `GET /sw.js`, not under `/static/`),
    since a service worker's default scope is the directory it's served
    from and Bubblewrap needs a stable `/manifest.json` URL; `sw.js`
    also gets a `Service-Worker-Allowed: /` header. `index.html` links
    the manifest/icons (plus a `theme-color` meta tag) and registers the
    service worker on load.
  - `scripts/build_static_site.py`'s two hardcoded string replacements
    were generalized into a regex over every
    `url_for('client.static', filename=...)` call, plus explicit
    handling for `client.manifest`/`client.service_worker`, and it now
    copies `manifest.json`/`sw.js` to the built site's root — GitHub
    Pages has no Flask routes to serve them dynamically.
  - `Client_test.py`: 5 new cases covering the manifest's content and
    mimetype, the service worker's mimetype and `Service-Worker-Allowed`
    header, that the icons are served, and that `index.html` actually
    references the manifest and registers the service worker.

### Changed

- Test suites now run via `python -m unittest discover` (stdlib) instead of
  pytest, matching the original spec. `.github/workflows/ci.yml` and the
  README's "Run the tests" section were updated to
  `python -m unittest discover -s <server|client>/test -p "*_test.py"`.
- Removed `pytest.ini`, `pyproject.toml` (isort's `profile = "black"`
  setting), root `conftest.py`, and the `pytest` dependency from
  `environment.yml`, since `unittest` discovery needs none of them.
- Aligned the project's structure and conventions with the sibling
  Priotask repo, after surveying it directly:
  - Switched from a `sys.path`-injection trick (in `server/test/__init__.py`
    / `client/test/__init__.py`) to absolute, package-rooted imports
    (`server.src.*`, `client.src.*`), with empty `server/__init__.py`,
    `server/src/__init__.py`, `client/__init__.py`, `client/src/__init__.py`
    marking the real package roots. Entry points now run as
    `python -m server.src.Server` / `python -m client.src.Client` (from the
    repo root) instead of `python server/src/Server.py`; `scripts/run.sh`,
    `install.sh`, `update.sh`, and `server/wsgi.py` were updated to match,
    and `server/wsgi.py` no longer needs a manual `sys.path.insert`.
  - Extracted demo-seeding into `server/src/services/DemoSeeder.py`
    (`seed_if_empty`), shared by `api/app.py`'s boot-time seeder
    (`JUSTFITTING_SEED_DEMO=true`) and a new standalone
    `scripts/seed_demo_data.py`, with `scripts/seed_demo_data.sh` now a
    thin wrapper around it — mirroring Priotask's
    `DemoSeeder.py`/`scripts/seed_demo_data.py` split instead of
    duplicating the seed logic inline in a shell heredoc.
  - `data/db/DB.py` now guards every query/execute/migrate/close call with
    a `threading.Lock()`, since `check_same_thread=False` disables
    Python's same-thread check but does not make one shared
    `sqlite3.Connection` safe for concurrent access from multiple request
    threads (Flask dev server/waitress/gunicorn can all do this). Added
    `DB_test.py::DBConcurrencyTest`, which hammers a shared `:memory:` DB
    from 8 threads to catch a regression.
  - DB-backed tests (`DB_test.py`, `UserManager_test.py`,
    `AuthService_test.py`, `LogManager_test.py`, `Api_test.py`) now use
    `DB(":memory:")` instead of a `tempfile`-backed file, removing the
    manual cleanup boilerplate.
  - `data/dto/{ProfileDTO,BodyLogDTO,MetricsDTO}.py` are now `@dataclass`
    wire types with a `from_domain(...)` constructor, serialized via
    stdlib `dataclasses.asdict(...)` in the route handlers, instead of
    plain `to_dict(...)` functions building dicts by hand.
  - Added `.vscode/settings.json` (`python.testing.unittestEnabled`) so
    the IDE's test explorer uses `unittest` instead of pytest.
- Moved `JustFitting_Documento_Final.pdf` into `docs/` and updated the
  references to it in `README.md` and `docs/product_capabilities_spec.md`.
- Repointed the Phase 2 Android plan from Chaquopy + on-device Flask +
  WebView to a **PWA wrapped in a Trusted Web Activity**, built with
  Google's Bubblewrap CLI against the already-hosted web client (GitHub
  Pages) and API (Render) — no server-side changes needed, since the
  existing production deployment already is the PWA origin. README's
  "Android app" section now describes 3 steps: (1) PWA manifest +
  service worker — done, see "Added" above; (2) HTTPS hosting + Digital
  Asset Links, and (3) generating the Android project with Bubblewrap —
  both not started, and (2) can't be filled in until (3) produces a
  package name and signing key. Removed the `JUSTFITTING_SERVE_CLIENT`
  merged-process feature from `api/app.py` and `.env.example` (it existed
  only to let an on-device Flask serve the client to a WebView, which the
  TWA approach doesn't need), and updated the
  `Server.py`/`Client.py`/`remote/RemoteFacade.py` docstrings that
  referenced the old plan.
