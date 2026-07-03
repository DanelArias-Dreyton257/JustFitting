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

The client suite includes Playwright browser tests (`client/test/browser/`,
Phase 1.6) that need Chromium downloaded once:
`python -m playwright install chromium`. `playwright` is already a Python
dependency in `environment.yml` — no Node.js involved.

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

The server and client runtime is Python-only: no Node.js, no build step.
Server and client are both small Flask apps that talk over HTTP:

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

Node.js/Capacitor (`package.json`, `capacitor.config.json`) is a dev-time
packaging tool for the Android app, not a runtime dependency — it bundles
the same static `dist/` client the web deployment already builds. See
**Android app** below.

### Repository layout

```
JustFitting/
├── environment.yml
├── package.json               # Capacitor Android packaging (dev-time only)
├── capacitor.config.json
├── Dockerfile.capacitor        # optional: Node/Capacitor CLI, isolated from conda
├── render.yaml
├── CHANGELOG.md
├── docs/composition_spec.md
├── .github/workflows/{ci,release}.yml
├── scripts/
├── dist/                       # generated static client, gitignored
├── android/                    # generated Capacitor project (after `npm run android:add`), committed
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
steps held constant by default (or trend-fit the same way,
`activity_model="trend"`, Phase 1.5), and intake assumed equal to the
previous week's target calories (`intake_is_real=false`) — see
`docs/composition_spec.md` for the full spec, the projection design
decision (`base_regression`), and the golden reference values
`CompositionEngine_test.py` is checked against.

Every constant above (`TEF`, the `7700` kcal/kg factor, the NEAT step
factor, and the Phase 1.3 alert thresholds) is a fixed `constants.py`
default that a user can override per-account (Phase 1.5, `GET`/`PUT
/api/users/me/settings`) — see `docs/composition_spec.md`.

**Health disclaimer**: body-fat figures are population-level estimates
(RFM, US Navy method, Deurenberg), not clinical measurements or medical
advice.

**Known limitations**:
- RFM and the U.S. Navy body-fat formulas above use male-only constants
  for every user (only Deurenberg adjusts for sex); results are
  systematically less accurate for female users. The app detects this and
  shows an in-app disclaimer wherever a female profile's body-fat figures
  are displayed (`renderSexDisclaimer` in `views.js`), rather than
  presenting a silently biased number. See "Future work" below.
- Password reset (`POST /api/auth/reset-password`) has no email or token
  verification: given a username/email that exists, it resets the
  password immediately. There's no mail server involved at all today. The
  client shows a disclaimer on the reset form pointing at this. See
  "Future work" below.

**Future work (unscheduled — not planned for the near term)**:
- A real female U.S. Navy body-fat formula. It needs a hip-circumference
  measurement (`waist + hip - neck`, different regression constants) that
  JustFitting has never collected, so it's a new logged field (DB column,
  wizard step, DTO, chart), not just a formula change. Deliberately left
  as a known limitation with a disclaimer (above) rather than scoped into
  any current phase.
- Email-verified password reset. Today `POST /api/auth/reset-password`
  resets on the spot, with only a client-side disclaimer warning that
  there's no verification. Gating it behind an emailed, single-use,
  short-lived token (and the SMTP/mail-sending infrastructure that needs)
  is the obvious next step, but isn't planned for the near term.

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

### Phase 1.2 — Visual tracking & UX completeness (done)

- The Dashboard's chart grid grew from 4 to 7 cards: waist/neck perimeters
  and daily steps (`chart-perimeters`, `chart-steps`) join weight, body
  fat %, fat/lean mass and calories. A new `drawMultiLineChart` in
  `charts.js` plots several series (with a small color-dot legend) on one
  `<svg>`, generalizing the old single-series `drawLineChart`. Waist/neck/
  steps aren't in `MetricsDTO`, so `app.js` merges `GET /api/logs` (raw
  `BodyLogDTO`, has them) with `GET /api/metrics/series` by `log_id`
  client-side — no server/DTO changes needed.
- A goal-trajectory chart (`chart-goal-trajectory`) plots actual weight
  (solid) against the weekly objective `Wobj` (dashed, `weight_objective_kg`
  — already computed per row by `Trajectory.compute_weight_objective` and
  returned in `MetricsDTO`), so real vs. planned progress is visible at a
  glance without any new backend work.
- The flat `#log-form` is now a 4-step guided wizard (Date & weight →
  Perimeters → Energy → Review) inside one `<form>`; `views.js`'s
  `showWizardStep`/`renderLogReview` toggle `<fieldset>` visibility and
  render a review summary, `app.js` gates `Next` on the current step's
  native input validity (`reportValidity()`). The final submit still posts
  the same payload to `POST /api/logs` — capture UX changed, not the
  contract.
- A new "Plan adjustment" view lets a user try a candidate target-BF/
  weekly-rate pair and see its effect on target calories, daily deficit,
  weeks-to-goal and goal weight *before* committing it, via a new
  read-only `GET /api/plan/preview?target_bf=&weekly_rate=` endpoint
  (`server/src/api/plan_routes.py`) that reuses
  `CompositionEngine.compute_row` with a candidate `ProfileParams` against
  the latest real log — no persistence, no cache invalidation. "Commit
  this plan" reuses the existing `PUT /api/users/me` (`GoalPlanManager`,
  historized as in Phase 1.1); the preview endpoint never writes.

### Phase 1.3 — Alerts & feedback engine (done)

- A new pure `services/composition/Alerts.py` module runs four detectors
  over an already-computed metrics series — no new engine computation and
  no `ENGINE_VERSION` bump, since every detector reads fields
  `CompositionEngine.compute_row` already produces:
  - **Implausible change**: surfaces the existing
    `CompositionEngine.IMPLAUSIBLE_WEEKLY_CHANGE_PCT` guard (previously
    only a Python `warnings.warn`) as a structured `warning` alert, reusing
    `weight_delta_pct`.
  - **Stagnation/plateau**: `STAGNATION_WEEKS` (3) consecutive real weeks
    with `|dW|` under `STAGNATION_THRESHOLD_KG` (0.15 kg).
  - **Excessive lean-mass loss**: over a `LEAN_LOSS_WINDOW_WEEKS` (4) real-week
    rolling window, lean mass makes up more than `MAX_LEAN_MASS_LOSS_SHARE`
    (35%) of a *net* weight loss (skipped entirely on a net gain).
  - **Significant deviation**: `|weight_gap_kg|` (`K_i`, actual weight vs.
    the weekly objective `Wobj`) beyond `SIGNIFICANT_DEVIATION_KG` (1.0 kg).

  All five thresholds are named constants in `constants.py`, next to the
  energy-model ones, as candidates for Phase 1.5's per-profile
  configurability.
- `GET /api/alerts` (`server/src/api/alerts_routes.py`) computes a user's
  series via a new shared `services/MetricsSeriesService.compute_series_for_user`
  (extracted from `/api/metrics`'s route, which had the same logic inlined)
  and runs `Alerts.detect_alerts` over it. Nothing new is persisted —
  alerts are recomputed on every read from existing logs/snapshots, the
  same way `/api/metrics/series` is.
- The Dashboard gained an alerts panel (`#dashboard-alerts`) above the stat
  tiles: `views.js`'s `renderAlerts` draws one bordered banner row per
  alert (red for `warning`, blue for `info`) and stays empty/hidden with no
  alerts, so a clean week costs no screen space.
- 11 `Alerts_test.py` cases (pure detector logic against synthetic
  `CompositionResult` series) plus 3 new `Api_test.py` cases covering
  `GET /api/alerts` end-to-end (empty with no logs, an implausible-change
  swing, a goal-trajectory deviation).

### Phase 1.4 — Adherence & reporting (done)

- `GET /api/metrics/adherence` (`metrics_routes.py`, new `AdherenceDTO`)
  surfaces `LogManager.compute_adherence` — mean `IntakeDiff` over
  `intake_is_real=true` rows only, plus the real-log count so the client
  can tell "no real-intake logs yet" apart from "0 kcal/day average" —
  and the Dashboard's stat-tile row now shows an "Adherence" tile
  (`±N kcal/day`) alongside the existing stats.
- Alerts are now persisted instead of recomputed and forgotten on every
  read: a new `alert_log` table (migration v8, `data/db/AlertLogDAO.py`,
  domain `AlertLog`, `AlertLogDTO`) records each detection deduped on
  `(user_id, type, date)`, via a shared `services/AlertSyncService
  .sync_alerts` (mirroring how `MetricsSeriesService` is already shared
  between `/api/metrics` and `/api/alerts`). `GET /api/alerts` now
  excludes acknowledged alerts by default (`?include_acknowledged=true`
  to see the full history) and a new `POST
  /api/alerts/<id>/acknowledge` dismisses one; the Dashboard's alerts
  panel gained a dismiss (×) button per alert.
- A new `GET /api/users/me/report` endpoint (`user_routes.py`) bundles
  profile, latest metrics, adherence, the full goal-plan history, the
  complete weekly series, and open alerts into one payload — richer
  than the existing raw JSON `/export` (which is unchanged and stays
  the backup/restore contract). A new "Report" view renders it as a
  readable summary with a **Print / Save as PDF** button
  (`window.print()` plus a `@media print` stylesheet that hides the
  nav/footer) — no new Python dependency, consistent with this repo's
  "no Node.js, no build step" architecture.
- The historized goal-plan timeline (`GET /api/users/me/goals`,
  implemented in Phase 1.1) is now surfaced in the UI: a "Goal history"
  table in the Plan view (start date, target BF%, weekly rate,
  active/past badge), and the same goal-change dates are drawn as
  dashed vertical markers on the Dashboard's goal-trajectory chart —
  so a user can see *when* and *why* their target calories shifted.
- `charts.js`'s three draw functions were reworked from index-spaced to
  date-spaced points: a date-based x-scale, ~4 gridlines/axis labels per
  axis, and hover tooltips (a small per-card `.chart-tooltip` div driven
  by `mousemove`, showing the date and each series' value under the
  cursor) — this was also the prerequisite for the goal-change markers
  above.

### Phase 1.5 — Account & model completeness (done)

- **Account recovery**: a direct, unverified password reset, not
  overwriting the existing authenticated change-password flow (`POST
  /api/users/me/password`, still requires the old password and is
  unaffected). `POST /api/auth/reset-password` `{identifier, new_password}`
  looks up the account by username or email and immediately updates the
  password (`services/PasswordResetService.py`), revoking every existing
  session for that user (`SessionDAO.delete_all_for_user`) and recording a
  redacted `audit_log` entry. There is no email/token verification step —
  see "Known limitations" and "Future work" above for the plan to add one.
  The client's auth view gained a "Forgot password?" toggle revealing the
  reset form, with an inline disclaimer about the missing verification
  step.
- **Sex-specific formulas — moved to "Known limitations"/"Future work",
  not implemented**: RFM and the U.S. Navy method stay male-calibrated for
  every user (Deurenberg already adjusts for sex). A real female Navy
  variant needs a hip-circumference measurement this app has never
  collected, which would mean a new logged field, wizard step, and chart,
  not just a formula change. Rather than half-build it or schedule it into
  a phase, this is documented as an unscheduled known limitation (see
  above) and a client-side disclaimer (`renderSexDisclaimer` in
  `views.js`) is shown wherever a female profile's body-fat figures are
  displayed, so the gap is visible instead of silent.
- **Configurable engine constants & alert thresholds, per user**: a single
  `EngineConstants` dataclass
  (`services/composition/models.py`) now covers both the energy-model
  constants (`tef`, `kcal_per_kg_fat`, `neat_step_factor`, and the
  implausible-change threshold) and the five Phase 1.3 alert thresholds,
  threaded as an optional parameter through `CompositionEngine.compute_row
  /compute_series`, `Alerts.detect_alerts`, and `Projection.project_series*`
  — omitting it reproduces today's fixed `constants.py` values exactly, so
  every existing golden test still passes unchanged. A new `EngineSettings`
  entity (migration v9, `data/db/EngineSettingsDAO.py`,
  `services/EngineSettingsManager.py`) historizes per-user overrides
  exactly like `GoalPlan` does for goals: every update deactivates the
  previous row, inserts a new one, audits each changed field, and
  invalidates the metrics cache so cached snapshots recompute under the
  new constants. `GET`/`PUT /api/users/me/settings` and `GET
  /api/users/me/settings/history` expose it; a new "Settings" client view
  edits it as percentages/raw values and lists the override history.
- **Configurable projection activity assumption**: `Projection
  .project_series_with_inputs` gained `activity_model="constant"` (default,
  today's carry-forward-the-last-value behavior, unchanged) or `"trend"`
  (fits the same OLS trend used for weight/waist/neck, clamped at 0). `GET`
  /`POST /api/projection` accept `?activity=`, persisted per saved run
  (`projections.activity_model`, migration v10); the Projection view
  gained a "Steps assumption" selector.
- **Alert-history browser**, noticed while building Phase 1.4:
  `GET /api/alerts?include_acknowledged=true` already returned the full
  history including dismissed alerts, but no UI browsed it. A new
  "Alerts" nav view (`renderAlertHistory` in `views.js`) lists every alert
  ever detected with an active/acknowledged badge and a dismiss button
  for the still-open ones, reusing the existing acknowledge endpoint.

### Phase 1.6 — Testing groundwork

- **Weighted projection model (done)**: `Projection.py` gained a
  `trend_model` parameter alongside `activity_model`/`base_regression` --
  `"ols"` (default, unchanged) or `"weighted_ols"`, a recency-weighted
  least-squares fit (`constants.WEIGHTED_TREND_DECAY`, default `0.85` per
  week) that leans on recent weeks more than older ones. Exposed via
  `?trend_model=` on `GET`/`POST /api/projection`, persisted per saved run
  (`projections.trend_model`, migration v11). No client UI selector yet
  (the API is usable today; a "Trend model" dropdown alongside the
  existing "Steps assumption" one in the Projection view is a natural
  follow-up).
- **Browser tests (done)**: Python-driven Playwright tests
  (`environment.yml` already listed `playwright` as a dependency ahead of
  this) exercising `views.js`'s DOM rendering and `api.js`'s network calls
  against real, in-process Flask apps (`client/test/browser/`, a shared
  `LiveServer` thread helper + a minimal test-harness Flask app pointed at
  the real static JS) -- not a Node-based test runner, keeping this inside
  the existing conda/`unittest` workflow. Run via the same
  `python -m unittest discover -s client/test -p "*_test.py"` command as
  every other client test, after a one-time
  `python -m playwright install chromium`; CI installs it automatically
  (`.github/workflows/ci.yml`).
- A fully-native client using the `remote/RemoteFacade` seam directly, as
  a longer-term alternative to the Capacitor Android app below — not
  planned, just kept possible.

## Android app

Phase 2 (scaffolding done; on-device build is a local step, see below):
ship the existing web client as an installable Android app by bundling
the same static `dist/` build **inside** the APK/AAB with
**[Capacitor](https://capacitorjs.com/)**, rather than opening a hosted
URL in a browser wrapper.

This repo's Android plan changed twice before landing here (see
`CHANGELOG.md` for the earlier Chaquopy + on-device-Flask attempt): the
most recent prior plan was a **Trusted Web Activity (TWA)** via Google's
Bubblewrap CLI — a thin Chrome wrapper that just opens the hosted PWA,
with the browser UI hidden once the domain is verified. Capacitor
replaces that: the UI ships inside the package instead of depending on a
reachable hosted client URL at runtime, while still keeping the API
remote over plain HTTP(S) — no on-device Flask, no WebView-only wrapper,
and no native UI rewrite. The Flask API stays exactly as deployed today
(Deployment, above); only the client is bundled differently.

```
scripts/build_static_site.py <API_URL>   # same build the web deploy uses
        |
dist/  (HTML/CSS/JS, api_base_url baked into index.html)
        |
capacitor.config.json  (webDir: "dist")
        |
npx cap sync android    # copies dist/ into the native Android project
        |
Android app: local UI, HTTP(S) calls to <API_URL>
```

### Setup

```bash
npm install                 # @capacitor/core, @capacitor/cli, @capacitor/android
npm run android:add         # one-time: scaffolds android/ via `npx cap add android`
```

**Running these in Docker instead of installing Node locally**: `Dockerfile.capacitor`
at the repo root isolates the Node/Capacitor CLI toolchain from the
conda-managed Python env (it includes a bare `python3` too, since the npm
scripts shell out to `scripts/build_static_site.py`, which is stdlib-only —
no pip deps needed for that to work in the container):

```bash
docker build -f Dockerfile.capacitor -t justfitting-capacitor .
docker run --rm -v "$PWD":/app justfitting-capacitor install
docker run --rm -v "$PWD":/app justfitting-capacitor run android:add
docker run --rm -v "$PWD":/app justfitting-capacitor run android:sync
```

This covers `install`/`android:add`/`android:sync` (they only touch files
under `node_modules/`, `dist/`, and `android/`). `npm run android:open`
launches Android Studio, a GUI app, and must be run natively on the host
afterward — it isn't a Docker command.

### Building the client for each target

The API base URL is injected the same way as the web build
(`scripts/build_static_site.py`, `window.JUSTFITTING_API_BASE_URL` in
`api.js`) — nothing new to learn, just a different target URL per case:

| Target | Command |
| --- | --- |
| Production (real device/release build) | `python scripts/build_static_site.py https://YOUR_PRODUCTION_API_URL` |
| Android emulator | `python scripts/build_static_site.py http://10.0.2.2:5000` (the emulator's alias for the host machine's `localhost`) — also `npm run build:web:android` |
| Real device on the same LAN | `python scripts/build_static_site.py http://LOCAL_MACHINE_LAN_IP:5000` |

Then sync the build into the native project and open it in Android Studio:

```bash
npm run android:sync        # build:web:android + `npx cap sync android`
npm run android:open        # `npx cap open android`
```

Run the app from Android Studio onto an emulator or a connected device.
After editing web client code, re-run `android:sync` (with whichever
`build_static_site.py` target you need) to refresh the bundled `dist/`
inside `android/`.

For a production release, run `build_static_site.py` with the production
URL, then `npx cap sync android` (skip the emulator-default script) before
building the signed AAB/APK in Android Studio.

### Network notes

- **Production must use HTTPS.** `capacitor.config.json` ships with no
  `cleartext` override, so Android's default cleartext-traffic block
  applies — this is intentional, not an oversight.
- **Local HTTP dev (emulator/LAN) needs cleartext enabled explicitly.**
  Android blocks plain-HTTP network requests by default since API 28. To
  test against `http://10.0.2.2:5000` or a LAN IP, temporarily add
  `"server": {"cleartext": true}` to `capacitor.config.json`, re-run
  `npx cap sync android`, and **revert it before any release build** —
  never ship `cleartext: true`.
- **CORS**: the server already reads `JUSTFITTING_CORS_ORIGINS` (see
  `server/src/api/app.py`) instead of hardcoding origins. Capacitor's
  Android WebView serves the bundled UI from the `https://localhost`
  origin by default, so if you lock `JUSTFITTING_CORS_ORIGINS` down to an
  allowlist (rather than the default `*`), include `https://localhost` in
  it or the app's API calls will be blocked by CORS.

### What's not built yet

- `android/` isn't in this repo — it's generated locally by
  `npm run android:add` and should then be committed (Capacitor's own
  convention: the native project holds Gradle/signing/manifest
  customizations that `cap sync` doesn't regenerate).
- Actually running the app on an emulator/device is a local step that
  needs Node.js and Android Studio/SDK installed — not something this
  repo's CI or a hosted environment can do for you.

### Future: local/offline data mode (design note, not implemented)

Today the Android app is purely a remote-API client, same as the web
app. A natural next step once this ships is a data-access layer inside
the client JS that can choose between **remote API mode** (today's
behavior, unchanged), **local storage mode** (logs/metrics cached or
entered offline, most likely via a Capacitor storage/SQLite plugin), and
a future **sync mode** reconciling the two. This is *only* a design
direction, not scoped work — running the full Flask server on-device is
explicitly out of scope unless a strong reason emerges later.

### Phase 2.1 — native capabilities (ideas, unscheduled)

Going native (even just as a Capacitor wrapper) unlocks a few
device-level capabilities that a browser tab can't offer, in service of
the project's core goal — full tracking with good visual feedback, and
full access to the computed body-report metrics. None of these are
scoped or scheduled; they're recorded here so they aren't lost:

- **Weekly-log reminder notifications** (`@capacitor/local-notifications`)
  — a scheduled local reminder to log the week's measurements, which
  today relies entirely on the user remembering to open the app.
- **Native share sheet for the Report view** — the existing `GET
  /api/users/me/report` + Print/Save-as-PDF flow (Phase 1.4) could use
  `@capacitor/share` to hand the exported report straight to another app
  (e.g. to a trainer or nutritionist) instead of only browser print.
- **Automatic steps import** (Android Health Connect / Google Fit) to
  replace today's manually-entered weekly step average with a real daily
  reading — directly improves the NEAT/TDEE inputs' accuracy.
- **Local/offline data mode** — see the design note above.

## The Team

Danel Arias — University of Deusto, Bilbao.
