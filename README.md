# JustFitting

A weekly body-composition tracker. Log a handful of easy home measurements
— weight, waist, neck, mean calorie intake, mean daily steps — and
JustFitting derives your body-fat %, fat/lean mass split, a full energy
model (BMR / NEAT / TDEE / target calories), a goal trajectory (target
weight, weekly deficit, weeks-to-goal), and a forecast of future weeks.

Try it: run `scripts/install.sh` then `scripts/run.sh`, open
`http://127.0.0.1:5500`, and log in with `admin` / `adminadmin` (seeded by
`scripts/seed_demo_data.sh`) to see a populated dashboard.

## Getting Started

```bash
scripts/install.sh          # create the conda env, .env, and justfitting.db
scripts/run.sh               # start the server (5000) and client (5500)
scripts/seed_demo_data.sh    # optional: admin/adminadmin + reference logs
```

Or manually (commands are run from the repo root):

```bash
conda env create -f environment.yml
conda activate justfitting
cp .env.example .env

python -m server.src.Server   # http://127.0.0.1:5000
python -m client.src.Client   # http://127.0.0.1:5500
```

Run the tests:

```bash
python -m unittest discover -s server/test -p "*_test.py"
python -m unittest discover -s client/test -p "*_test.py"
```

## Scripts

All scripts live in `scripts/` and `cd` to the repo root themselves.

| Script | Purpose |
| --- | --- |
| `install.sh` | Create the `justfitting` conda env and `justfitting.db`. Run once. |
| `run.sh` | Start server + client together; Ctrl+C stops both. |
| `update.sh` | `conda env update --prune`; apply pending DB migrations. |
| `reset_db.sh [path]` | Delete the SQLite file (confirms unless `FORCE=1`). |
| `seed_demo_data.sh` | Register `admin`/`adminadmin` and seed the Danel reference series. No-op if already seeded. |
| `uninstall.sh [path]` | Remove the conda env and optionally the DB. |
| `build_static_site.py [api_base_url]` | Build the client into `dist/` for a static host (e.g. GitHub Pages). |

Set `JUSTFITTING_SEED_DEMO=true` to auto-seed the Danel demo on an empty
DB at server boot, so a fresh/ephemeral deploy is always demoable.

## Deployment

- **CI** (`.github/workflows/ci.yml`) runs both test suites on every push
  and pull request.
- **Release** (`.github/workflows/release.yml`) triggers on a `vX.Y.Z` tag:
  re-runs CI as a gate, builds the client with `scripts/build_static_site.py`
  and publishes it to **GitHub Pages**, optionally pings a **Render** deploy
  hook for the API (see `render.yaml`), and cuts a GitHub Release with
  auto-generated notes.
- **One-time setup**: set the `JUSTFITTING_API_BASE_URL` repo variable
  (client build target) and, if deploying the API to Render, the
  `RENDER_DEPLOY_HOOK_URL` secret.

### Releasing a version

```bash
git tag vX.Y.Z
git push origin vX.Y.Z
```

## Versioning

[Semantic Versioning](https://semver.org/). Releases are git tags; see
`CHANGELOG.md` ([Keep a Changelog](https://keepachangelog.com/) format).

## Architecture

Python-only, no Node.js, no build step. Server and client are both small
Flask apps that talk over HTTP:

- **Server** (`http://localhost:5000`) — persistence, business logic, the
  calculation engine. Bearer-token auth with DB-persisted, sliding-expiry
  sessions.
- **Client** (`http://localhost:5500`) — a Flask app serving a static
  HTML/CSS/vanilla-JS shell. All app logic runs client-side in the browser.

The client JS mirrors the server's DAO/service split:

- `api.js` — the only module that `fetch`es the API.
- `session.js` — bearer token in `localStorage`.
- `views.js` — pure DOM rendering; no fetch, no state.
- `app.js` — controller; holds all app state, wires DOM events to `api.js`/`views.js`.
- `charts.js` — hand-rolled SVG charts (no charting library dependency).

The `services/composition/` engine is pure and deterministic: each
formula lives in its own module (`Anthropometry`, `BodyFat`, `EnergyModel`,
`Trajectory`, `Projection`), orchestrated in compute order by
`CompositionEngine`, with every constant named in `constants.py`. See
**The Composition Model** below and `docs/composition_spec.md` for the
full, authoritative spec.

### Repository layout

```
JustFitting/
├── environment.yml
├── render.yaml
├── CHANGELOG.md
├── docs/composition_spec.md
├── .github/workflows/{ci,release}.yml
├── scripts/
├── client/
│   ├── src/
│   │   ├── Client.py            # Flask entry point (port 5500)
│   │   └── webapp/{templates,static/{css,js,icons,manifest.json,sw.js}}
│   └── test/
└── server/
    ├── wsgi.py
    ├── requirements-prod.txt
    ├── src/
    │   ├── Server.py             # Flask entry point (port 5000)
    │   ├── api/                  # app factory, auth guard, route blueprints
    │   ├── data/{db,domain,dto}  # DB.py + DAOs, domain models, DTOs
    │   ├── remote/                # RemoteFacade/TokenManager seam for a future native client
    │   └── services/
    │       └── composition/       # the calculation engine
    └── test/
```

## The Composition Model

Static params: height `H` (cm), sex `g` (1 male / 0 female), `birthdate`,
target body-fat fraction `tau`, weekly target rate `r` (negative = loss).
Weekly inputs: date `t_i`, weight `W_i`, waist `c_i`, neck `n_i`, intake
`E_i`, steps `s_i`.

```
age_i      = floor((t_i - birthdate) / 365.25)
BMI_i      = round(W_i / (H/100)^2, 2)
RFM_i      = (64 - 20 * (H / c_i)) / 100
Navy_i     = (495 / (1.0324 - 0.19077*log10(c_i - n_i) + 0.15456*log10(H)) - 450) / 100
Deur_i     = (1.2*BMI_i + 0.23*age_i - 10.8*g - 5.4) / 100
BF_i       = 0.50*RFM_i + 0.25*Navy_i + 0.25*Deur_i

FatMass_i  = round(W_i * BF_i, 2)
LeanMass_i = round(W_i * (1 - BF_i), 2)
BMR_i      = 500 + 22 * LeanMass_i
NEAT_i     = 0.5 * W_i * (s_i / 1000)
TDEE_i     = (BMR_i + NEAT_i) / (1 - TEF)

Wobj_i     = W_{i-1} * (1 + r)                  # Wobj_1 = W_1
Pi_i       = W_{i-1} - Wobj_i                   # base 0 at i=1
DailyDeficit_i = (Pi_i * 7700) / 7
TargetCal_i    = (BMR_i + NEAT_i - DailyDeficit_i) / (1 - TEF)
Wfinal_i   = LeanMass_i / (1 - tau)
Weeks_i    = ln(W_i / Wfinal_i) / ln(1 - r)
```

Danel worked example (`H=176, sex=1, birthdate=2001-08-22, target_bf=0.15,
weekly_rate=-0.005`), last real record 2026-06-26 (`W=90.7, waist=80.0,
neck=35.0, steps=5000`):

```
BMI 29.28 | BF 19.91% | FatMass 18.06 kg | LeanMass 72.64 kg
BMR 2098.08 | TDEE 2583.14 | TargetCal 2027.03
Wobj 90.545 | DailyDeficit 500.5 | Wfinal 85.459 | Weeks 11.93
```

Future weeks are forecast with an OLS linear trend (weight/waist/neck),
steps held constant, and intake assumed equal to the previous week's
target calories (`intake_is_real=false`) — see `docs/composition_spec.md`
for the full spec, the projection design decision (`base_regression`), and
the golden reference values `CompositionEngine_test.py` is checked against.

**Health disclaimer**: body-fat figures are population-level estimates
(RFM, US Navy method, Deurenberg), not clinical measurements or medical
advice.

## Roadmap: body-composition module capabilities

Phase 1 (this repo, done) covers the calculation engine end-to-end and a
working server + client, verified against the golden Danel reference
values. The consolidated technical spec (`docs/JustFitting_Documento_Final.pdf`,
v2.0) additionally defines product capabilities that Phase 1 doesn't
cover yet. They're grouped below into sub-phases so they can be picked up
independently, in roughly the order that unlocks the most value first;
full detail, status per item, and the recommended data model are in
`docs/product_capabilities_spec.md`.

### Phase 1.1 — Data model & audit hardening (done)

- `GoalPlan` is split out of `UserProfile` into its own historized entity
  (`goal_plans`: `goal_id, user_id, target_bf, weekly_rate, start_date,
  active, created_at`, `data/db/GoalPlanDAO.py`, `services/GoalPlanManager.py`).
  Every target-BF/weekly-rate change deactivates the previous row and
  inserts a new one instead of overwriting in place; `GET
  /api/users/me/goals` returns the full history, newest first. The
  `users` table's old `target_bf`/`weekly_rate` columns are gone (backfilled
  into an initial active goal plan by migration v4); `GET`/`PUT
  /api/users/me` keep returning `target_bf`/`weekly_rate` by joining in the
  active goal, so existing clients are unaffected.
- An audit trail (`audit_log` table, `data/db/AuditLogDAO.py`) records
  every profile field edit, goal-plan change, and body-log field edit:
  user, entity, field, previous value, new value, timestamp, and the
  engine version where applicable. `GET /api/users/me/audit-log` exposes
  it; it's also folded into `GET /api/users/me/export`.
- `CalculatedMetrics`/`EnergyPlan` results are cached per log, keyed by
  `(log_id, engine_version)` (`metrics_snapshots` table,
  `data/db/MetricsSnapshotDAO.py`, `services/MetricsCache.py`). A read
  recomputes only when a log is missing its snapshot at the current
  `CompositionEngine.ENGINE_VERSION`; any log create/update/delete or
  goal-plan change invalidates the affected user's cache so the next read
  repopulates it. `MetricsDTO` now carries `log_id`/`engine_version`.
- Forecast runs can be persisted (`projections` table,
  `data/db/ProjectionDAO.py`, `services/ProjectionService.py`):
  `POST /api/projection` saves the current forecast under a `run_id` (with
  `estimated_weight/waist/neck`, `source_model`, `base_regression`);
  `GET /api/projections` lists saved runs and `GET
  /api/projections/<run_id>` retrieves one, so a forecast can be inspected
  later without recomputing. `GET /api/projection` (no persistence) is
  unchanged for the live-preview use case.

### Phase 1.2 — Visual tracking & UX completeness

- Add waist/neck perimeter and steps charts to the Dashboard (today only
  weight, body fat %, fat/lean mass and calories are charted).
- Add a goal-trajectory comparison chart: actual weight vs. the weekly
  `Wobj` target line, so real vs. planned progress is visible at a glance.
- Turn the flat weekly-log form into a guided, multi-step capture flow.
- Add a dedicated "Plan adjustment" view: shows the effect of a
  calorie-target change on weeks-to-goal before committing it.

### Phase 1.3 — Alerts & feedback engine

- Surface the existing implausible-weekly-change guard
  (`CompositionEngine.IMPLAUSIBLE_WEEKLY_CHANGE_PCT`, today only a Python
  `warnings.warn`) as a structured API/UI alert.
- Add stagnation/plateau detection (N consecutive weeks with `|dW|` under
  a configurable threshold).
- Add excessive-lean-mass-loss detection (lean mass falling faster than a
  configurable share of total weight lost).
- Add significant-deviation alerts (actual weight diverging from `Wobj`
  by more than a configurable margin).
- Expose all of the above through a notifications endpoint and a UI
  alerts panel/banner.

### Phase 1.4 — Adherence & reporting

- Add `GET /api/metrics/adherence` (or fold it into `/latest`) surfacing
  `LogManager.compute_adherence` — mean `IntakeDiff` over
  `intake_is_real=true` rows only — and show it on the Dashboard.
- Add exportable technical reports/summaries for the user, a trainer, or
  a nutritionist (e.g. a printable/PDF report), beyond today's raw JSON
  export/import.

### Phase 1.5 — Account & model completeness

- Account recovery / forgot-password flow (email-based reset).
- Sex-specific RFM and U.S. Navy formula variants — both are currently
  hardcoded to the male-constant form (Deurenberg already varies by sex);
  either add the female variants or explicitly declare the male-only
  scope in the product.
- Make the energy constants (`KCAL_PER_KG_FAT`, `TEF`, the NEAT step
  factor) configurable per profile/admin rather than fixed code
  constants.
- Make the projection's activity assumption configurable (today steps
  are always carried forward as a constant).

### Phase 1.6 — Testing groundwork

- Weighted or non-linear projection models beyond OLS.
- Playwright JS unit tests for `views.js`/`api.js`.
- A fully-native client using the `remote/RemoteFacade` seam directly, as
  a longer-term alternative to the PWA/TWA Android app below — not
  planned, just kept possible.

## Android app

Phase 2 (not yet built): ship the existing hosted web client as an
installable Android app via a **Trusted Web Activity (TWA)**, built with
Google's **Bubblewrap** CLI. No on-device Flask, no WebView, no native
HTTP client — the Android app is a thin wrapper that opens the same
hosted PWA in Chrome, with the browser UI hidden once the domain is
verified:

```
Flask backend + HTML/CSS/JS
        |
Hosted at https://yourdomain.com  (client on GitHub Pages, API on Render
        |                          -- both already set up, see Deployment)
PWA manifest + service worker
        |
Bubblewrap generates Android project
        |
Android app opens your Flask PWA as a TWA
```

Steps:

1. **PWA groundwork** (done) — `client/src/webapp/static/manifest.json`
   (name, icons, `start_url: "/"`, `display: standalone`, theme/background
   color, `scope: "/"`) and an app-shell service worker (`static/sw.js`,
   stale-while-revalidate for this site's own static assets; API calls to
   a different origin are left untouched). Both are served at the site
   *root* — `GET /manifest.json` and `GET /sw.js` in `Client.py`, not
   under `/static/`, since a service worker's default scope is the
   directory it's served from and Bubblewrap wants a stable
   `/manifest.json` URL — and linked/registered from `index.html`.
   `scripts/build_static_site.py` resolves the same `url_for(...)` calls
   and copies both files to the built site's root for GitHub Pages, which
   has no Flask routes to serve them dynamically. This already makes the
   client installable and usable offline, independent of Android.
2. **HTTPS hosting + Digital Asset Links** (not started): the client must
   be served over HTTPS at a stable domain (the existing GitHub Pages
   deploy in `release.yml` already qualifies, or any custom domain
   pointed at it). Add `/.well-known/assetlinks.json` at that origin,
   declaring the Android app's package name and signing-key fingerprint,
   so Android can verify the app owns the site and hide the address bar
   (this is what makes it a TWA rather than just "a browser bookmark").
   Can't be filled in until step 3 produces a package name + keystore.
3. **Generate the Android project** (not started): `npx @bubblewrap/cli
   init --manifest=https://yourdomain.com/manifest.json` scaffolds an
   Android Studio project pointed at the hosted PWA; `bubblewrap build`
   produces a signed APK/AAB ready for internal testing or the Play
   Store.

Because the client and API are already deployed as two independently
hosted HTTPS services (Deployment, above), no server-side changes are
needed for this — the same production deployment *is* the PWA.

## The Team

Danel Arias — University of Deusto, Bilbao.
