# JustFitting
[![CI](https://github.com/DanelArias-Dreyton257/JustFitting/actions/workflows/ci.yml/badge.svg)](https://github.com/DanelArias-Dreyton257/JustFitting/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/DanelArias-Dreyton257/JustFitting)](https://github.com/DanelArias-Dreyton257/JustFitting/releases/latest)

A weekly body-composition tracker. Log a handful of easy home measurements
— weight, waist, neck, mean calorie intake, mean daily steps — and
JustFitting derives your body-fat %, fat/lean mass split, a full energy
model (BMR / NEAT / TDEE / target calories), a goal trajectory (target
weight, weekly deficit, weeks-to-goal), and a forecast of future weeks.

Try it out! https://danelarias-dreyton257.github.io/JustFitting/ — log in
with `admin_cut` / `adminadmin` (a cut, resembling Danel) or `admin_bulk` /
`adminadmin` (a bulk, resembling Sergio) to see a populated dashboard. The
API is on Render's free tier, so the first request after idling may take
up to a minute to wake it up.

Or run it locally: `scripts/install.sh` then `scripts/run.sh`, open
`http://127.0.0.1:5500`, and log in with the same demo accounts — both
seeded by `scripts/seed_demo_data.sh`.

## Getting Started

```bash
scripts/install.sh          # create the conda env, .env, and justfitting.db
scripts/run.sh               # start the server (5000) and client (5500)
scripts/seed_demo_data.sh    # optional: admin_cut/admin_bulk + reference logs
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

The client suite includes Python-driven Playwright browser tests
(`client/test/browser/`) that need Chromium downloaded once:
`python -m playwright install chromium`. `playwright` is a Python
dependency in `environment.yml` — no Node.js involved for testing.

## Scripts

All scripts live in `scripts/` and `cd` to the repo root themselves.

| Script | Purpose |
| --- | --- |
| `install.sh` | Create the `justfitting` conda env and `justfitting.db`. Run once. |
| `run.sh` | Start server + client together; Ctrl+C stops both. |
| `update.sh` | `conda env update --prune`; re-apply the (idempotent) DB schema. |
| `reset_db.sh [path]` | Delete the SQLite file (confirms unless `FORCE=1`). |
| `seed_demo_data.sh` | Register `admin_cut`/`admin_bulk` (both `adminadmin`) and seed their Danel (cut) and Sergio (bulk) reference series. No-op per-account if already seeded. |
| `uninstall.sh [path]` | Remove the conda env and optionally the DB. |
| `build_static_site.py [api_base_url]` | Build the client into `dist/` for a static host or the Android app (see **Android app** below). |

Set `JUSTFITTING_SEED_DEMO=true` to auto-seed both demo accounts on an
empty DB at server boot, so a fresh/ephemeral deploy is always demoable.

## Deployment

`main` is the deployed branch. Every push and pull request runs the CI
workflow (`.github/workflows/ci.yml`): sets up the `justfitting` conda
environment exactly as described above, then runs both test suites.
Pushing a tag matching `vX.Y.Z` runs the release workflow
(`.github/workflows/release.yml`), which re-runs CI as a gate and, only
if it's green:

- **Client**: builds `client/src/webapp/{templates,static}` into a static
  `dist/` folder via `scripts/build_static_site.py` (`JUSTFITTING_API_BASE_URL`
  baked in from the repo variable of the same name) and publishes it to
  **GitHub Pages**.
- **Server**: calls Render's deploy hook (`RENDER_DEPLOY_HOOK_URL` repo
  secret) to redeploy the Flask API — described by `render.yaml` — on
  **Render.com**.
- Creates a GitHub Release for the tag with auto-generated notes.

### Releasing a new version

1. Merge `development` into `main` via a pull request.
2. Update [`CHANGELOG.md`](CHANGELOG.md) (move `[Unreleased]` items under
   a new version heading).
3. Tag `main` and push the tag: `git tag vX.Y.Z && git push origin vX.Y.Z`.

### One-time environment setup

These are one-off steps in the GitHub/Render UIs, not run by any workflow:

1. **GitHub Pages** requires GitHub Pro/Team/Enterprise on a private repo
   (Free plan can't publish Pages from a private repo). Repo Settings →
   Pages → Source = "GitHub Actions".
2. Create a Render web service from this repo (branch `main`); it reads
   `render.yaml`. Turn off Render's own auto-deploy-on-push in its
   dashboard — deploys are meant to happen only through the tag-triggered
   workflow above (`render.yaml` also sets `autoDeploy: false`).
3. Add the Render service's public URL as the repo variable
   `JUSTFITTING_API_BASE_URL` (Settings → Secrets and variables → Actions
   → Variables).
4. Add the Render service's Deploy Hook URL as the repo secret
   `RENDER_DEPLOY_HOOK_URL` (Settings → Secrets and variables → Actions →
   Secrets).

CORS needs no setup: the server allows any origin by default
(`JUSTFITTING_CORS_ORIGINS`, unset, defaults to `*`), the same choice
Priotask makes -- auth is a bearer token attached by the client itself,
not a cookie, so there's no CSRF exposure from allowing any origin.

### Known limitation

Render's free tier has an ephemeral filesystem, so `justfitting.db`
resets on every redeploy and likely on every spin-down/spin-up cycle
after 15 minutes of inactivity. Fine for demoing v1.0.0; not a place to
keep real data yet. To keep the deployed instance demoable through those
resets, the Render service runs with `JUSTFITTING_SEED_DEMO=true`, which
auto-seeds both demo accounts (`admin_cut`/`admin_bulk`) on every boot of
an empty database.

## Versioning

[Semantic Versioning](https://semver.org/) (`MAJOR.MINOR.PATCH`).
Releases are git tags (`vX.Y.Z`); see [`CHANGELOG.md`](CHANGELOG.md)
([Keep a Changelog](https://keepachangelog.com/) format) for what changed
in each one.

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
the same static `dist/` client the web deployment already builds. Node
itself is a conda dependency (`environment.yml`), same as Python. See
**Android app** below.

### Repository layout

```
JustFitting/
├── environment.yml
├── package.json               # Capacitor Android packaging (Node from environment.yml)
├── capacitor.config.json
├── render.yaml
├── CHANGELOG.md
├── docs/composition_spec.md
├── .github/workflows/{ci,release}.yml
├── scripts/
├── dist/                       # generated static client, gitignored
├── android/                    # Capacitor Android project, committed
├── client/
│   ├── src/
│   │   ├── Client.py            # Flask entry point (port 5500)
│   │   └── webapp/{templates,static/{css,js,icons,manifest.json,sw.js}}
│   └── test/
│       └── browser/             # Playwright browser tests
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

Future weeks are forecast with a linear trend fit — plain or
recency-weighted OLS, selectable via `trend_model` — for weight/waist/neck;
steps are held constant by default or trend-fit the same way
(`activity_model="trend"`); intake is assumed equal to the previous week's
target calories (`intake_is_real=false`). See `docs/composition_spec.md`
for the full spec, the regression-base design decision (`base_regression`),
and the golden reference values `CompositionEngine_test.py` is checked
against.

Every constant above (`TEF`, the `7700` kcal/kg factor, the NEAT step
factor, and the alert thresholds used by the alerts engine below) is a
fixed `constants.py` default that can be overridden per-account
(`GET`/`PUT /api/users/me/settings`) — see `docs/composition_spec.md`.

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
- **Dashboard perimeter/steps charts don't expand a daily-logged week.**
  Since Phase 1.2, `app.js`'s `refreshDashboard` merges `GET /api/logs`
  (raw, one row per day for a daily-granularity account) with `GET
  /api/metrics/series` (one row per *week*, by `log_id`, per Phase 3.3's
  resampling) client-side. A daily-logging week's waist/neck/steps chart
  point only lands on the resampled week's representative day; the other
  logged days in that week don't get their own point. This is a known,
  documented consequence of the engine staying weekly-cadence, not a bug
  -- fixing it would mean reworking that merge to resolve by ISO week
  instead of `log_id`, or building a real per-day chart on top of
  Phase 3.3's now-available `LogResampler.daily_view`. Not scoped into a
  phase since the raw log table already shows every logged day correctly.
- **`LogResampler.daily_view` has no route or UI yet.** Phase 3.3 shipped
  and unit-tested the symmetric daily-view expansion (a weekly log's
  values carried across the days it covers), but nothing in the app
  displays a per-day view today, so it isn't wired to an endpoint. It's
  the natural data source for the still-unscheduled Phase 2.1 ideas
  (automatic steps import, a real per-day target-calorie figure).

## Roadmap: body-composition module capabilities

The consolidated technical spec (`docs/JustFitting_Documento_Final.pdf`,
v2.0) defines the product capabilities this roadmap tracks; full detail,
status per item, and the recommended data model are in
`docs/product_capabilities_spec.md`. Phases are grouped in roughly the
order that unlocked the most value first — all of Phase 1's sub-phases are
done.

A second source document, `docs/JustFitting_Oleada2_Sergio.pdf` (v1.0),
specifies an entirely new bulk/volume module (eight capabilities, F1–F8)
on top of the same core engine; see Phase 3 below, and the "Wave 2"
sections of `docs/composition_spec.md` (formulas) and
`docs/product_capabilities_spec.md` (capabilities, data model,
validations) for the full spec. A **third** source document,
`docs/JustFitting_TEF_Macronutrientes.pdf` (v1.0), adds a ninth
capability (F9) on top of that module: real TEF computed from logged
carb/fat/protein grams instead of a flat 10% guess — see Phase 3.4, which
also ships one capability beyond either source document (evidence-based
protein/fat intake targets by body mass). **F1–F9 are all done as of
Phase 3.4 — Phase 3 (Wave 2) is complete**, with nothing left
unscheduled from either source doc's own capability list.

### Phase 1 — Core engine (done)

The calculation engine, server, and client, end-to-end, verified against
the golden reference values above.

### Phase 1.1 — Data model & audit hardening (done)

- Goal plans are historized: `GET /api/users/me/goals` returns the full
  history of target-BF/weekly-rate changes, not just the current one.
- Every profile, goal-plan, and log edit is audited:
  `GET /api/users/me/audit-log`.
- Computed metrics are cached per log and invalidated automatically on
  relevant changes (a log edit, a goal change).
- Forecast runs can be saved and re-fetched later without recomputing:
  `POST`/`GET /api/projection(s)`.

### Phase 1.2 — Visual tracking & UX completeness (done)

- Dashboard chart grid: weight, body fat %, fat/lean mass, calories,
  waist/neck perimeters, steps, and actual-vs-goal trajectory.
- Weekly log capture is a guided 4-step wizard (date/weight → perimeters →
  energy → review) instead of one long form.
- A "Plan adjustment" view previews a candidate target-BF/weekly-rate pair
  before committing to it: `GET /api/plan/preview`.

### Phase 1.3 — Alerts & feedback engine (done)

- Automatic detectors for an implausible weekly change, stagnation,
  excessive lean-mass loss, and significant deviation from the goal
  trajectory: `GET /api/alerts`.
- A Dashboard alerts panel that stays empty (no space used) on a clean
  week.

### Phase 1.4 — Adherence & reporting (done)

- Adherence tracking computed only over real (non-assumed) intake:
  `GET /api/metrics/adherence`.
- Alerts are persisted and dismissible instead of recomputed on every
  read: `POST /api/alerts/<id>/acknowledge`.
- A full progress report — profile, latest metrics, adherence, goal
  history, weekly series, open alerts — with a Print/Save-as-PDF button:
  `GET /api/users/me/report`. Later folded in every Wave 2 read-side
  view (gain-quality, energy-balance, increment-analytics, TEF breakdown,
  macro targets) alongside the JSON `/export`, once those existed — see
  Phase 3.4.
- Goal-change history is visible in the UI, including as markers on the
  goal-trajectory chart.

### Phase 1.5 — Account & model completeness (done)

- Direct (unverified) password reset: `POST /api/auth/reset-password` —
  see "Known limitations" above.
- Sex-specific body-fat formulas are an explicit, documented known
  limitation, not implemented — see above.
- Engine constants (TEF, kcal/kg-fat factor, NEAT step factor) and every
  alert threshold are configurable per account, historized like a goal
  plan: `GET`/`PUT /api/users/me/settings`.
- The projection's steps assumption is configurable — held constant or
  trend-fit — via `activity_model`.
- An alert-history browser view, listing every alert ever detected.

### Phase 1.6 — Testing & modeling (done)

- A recency-weighted OLS trend model for projections, selectable
  alongside the plain-OLS default via `trend_model` on `GET`/`POST
  /api/projection`.
- Python-driven Playwright browser tests for the client JS
  (`client/test/browser/`) — no Node.js involved, run via the same
  `unittest discover` command as every other test.

### Phase 2 — Android app (done — see below)

JustFitting ships as an installable Android app via Capacitor, bundling
the client UI inside the APK while the API stays remote. See
**Android app** below for the full setup, build, and distribution
workflow.

### Phase 2.1 — Native capability ideas (unscheduled)

Going native unlocks a few device-level capabilities a browser tab can't
offer. None of these are scoped or scheduled; recorded here so they
aren't lost:

- **Weekly-log reminder notifications** (`@capacitor/local-notifications`)
  — a scheduled local reminder to log the week's measurements.
- **Native share sheet for the Report view** — hand the exported report
  straight to another app (e.g. a trainer or nutritionist) via
  `@capacitor/share`, instead of only browser print.
- **Automatic steps import** (Android Health Connect / Google Fit) to
  replace the manually-entered weekly step average with a real daily
  reading — directly improves the NEAT/TDEE inputs' accuracy.
- **Local/offline data mode** — see the design note in the Android app
  section below.

### Phase 3 — Wave 2: bulk/volume engine foundation (done)

Source: `docs/JustFitting_Oleada2_Sergio.pdf` (F1, F4, F8). Lands the
per-account configuration and BMR model choice everything else in Wave 2
builds on, without touching any existing (cut-mode) computed values:

- Goal engine grows a `direction = cut | bulk` label derived from
  `weekly_rate`'s sign (`GoalPlan.direction`, a `@property`, no new
  column), exposed on `GET /api/users/me` and `GET /api/users/me/goals`. A
  new `bulk_rate_out_of_range` detector (`services/composition/Alerts.py`)
  flags — via the existing persisted/dismissible `GET /api/alerts`, not a
  blocking exception — a bulk goal whose `weekly_rate` falls outside the
  recommended `[0.25%, 0.5%]` range. The Plan view relabels the existing
  deficit figure as "Daily surplus" for a bulk goal and shows a
  Cut/Bulk badge; the Goal history table gains a Direction column.
- A second BMR model, Mifflin–St Jeor (`EnergyModel.compute_bmr_mifflin`),
  selectable via `bmr_model` (`"cunningham"` default | `"mifflin"`) on the
  same per-account `EngineSettings` object as every other energy-model
  constant — not a per-request query param like `trend_model`/
  `activity_model`, since BMR choice affects every metrics computation, not
  just an ephemeral forecast.
- `EngineSettings` grows Wave 2's calibration constants — `delta` (fat
  offset), `ffmi_coef` (promoted from a literal in `Anthropometry.py`),
  `w_rfm`/`w_navy`/`w_deur` (promoted from fixed `constants.py` globals,
  guarded to sum to `1.0` when all three are overridden together),
  `lean_tissue_kcal_per_kg` and `fat_ratio_ideal` (both unused until Phase
  3.2/3.1 respectively, shipped now so `engine_settings` doesn't need a
  second migration later) — historized like every other per-account
  constant (migration 12), defaulting to values that reproduce today's
  numbers exactly, never Sergio's own calibration. `GET`/`PUT
  /api/users/me/settings` pick up all seven fields automatically (the
  route is driven off `EngineSettingsManager.FIELDS`); the Settings view
  gained a "Body-fat & BMR calibration" section.
- Bulk mode reuses the existing deficit/target-calorie formula chain
  unmodified — `Pi_i` already goes negative (a surplus) when the weekly
  rate is positive (verified in `CompositionEngine_test.py` with a
  Mifflin-BMR bulk profile). `docs/composition_spec.md`'s "Formula
  reconciliation" works out why TEF should stay a divisor (not the
  multiplier the source spreadsheet uses) for both directions, so the only
  actual formula addition across all of Wave 2 is the cardio/EAT term
  from Phase 3.1 below, default `0`.

### Phase 3.1 — Wave 2: cardio input & gain-quality tracking (done)

Source: `docs/JustFitting_Oleada2_Sergio.pdf` (F2, F3). The central new
capability of the module — "is this bulk clean?":

- A weekly `cardio_kcal` (EAT) field (`body_logs`, migration 13, default
  `0`) folded into TDEE/target-calories for every account, not just
  bulk-mode ones — `EnergyModel.compute_tdee`/`compute_target_calories`
  gained a trailing `eat` parameter inside the existing divisor formula,
  so `cardio_kcal=0` (every pre-existing log) is byte-for-byte unchanged.
  Captured in the log wizard's "Energy" step and shown in the log table.
- A gain-quality panel (`GET /api/metrics/gain-quality`, a new pure
  `services/composition/GainQuality.py` module — a read-side derived view
  over an already-computed series, like `Alerts.py`, not a
  `CompositionResult`/`ENGINE_VERSION` change): weekly and cumulative
  lean/fat split of the week-over-week weight change, with a 25/75
  ideal-ratio indicator. The Dashboard gained a signed weekly lean/fat
  delta chart (`drawDivergingBars`, a new `charts.js` primitive — unlike
  the existing `drawStackedBars` used for fat/lean *levels*, a delta can
  go negative on a loss week) and a cumulative-fat-ratio-vs-ideal stat
  tile.

### Phase 3.2 — Wave 2: energy reconciliation & increment analytics (done)

Source: `docs/JustFitting_Oleada2_Sergio.pdf` (F5, F7). Closes the loop
between the energy model and what's actually being measured:

- An energy-reconciliation check (`GET /api/metrics/energy-balance`, a new
  pure `services/composition/EnergyReconciliation.py` module) comparing the
  surplus implied by intake (`E_i - TDEE_i`) against the surplus implied by
  *next* week's measured tissue change (reusing `GainQuality`'s lean/fat
  deltas rather than re-deriving them), with its error -- and a rolling
  mean of it (`constants.ENERGY_RECONCILIATION_WINDOW_WEEKS`, default 4
  weeks) -- surfaced to the user. Like `GainQuality`/`Alerts`, this is a
  read-side derived view over an already-computed series, so no
  `ENGINE_VERSION` bump was needed. Inherently one-week-lagged: the most
  recently logged week has no error yet, and a week with only assumed
  (not real) intake has no ingested-surplus figure either, though its
  tissue-side figure still computes.
- Real-increment analytics (`GET /api/metrics/increment-analytics`, a new
  pure `services/composition/IncrementAnalytics.py` module): an expanding
  mean of the actual weekly increment (`weight_delta_pct`, already
  computed) and its normalized deviation from the account's active goal
  rate, over real (non-projected) weeks, skipping the first week's
  base-case `0.0`.
- Two new alerts extending Phase 1.3's engine (`services/composition/Alerts.py`):
  a high fat-ratio week on a bulk goal ("dirty bulk", using `GainQuality`'s
  `fat_ratio` against `EngineConstants.fat_ratio_ideal`) and a reconciliation
  error above a new, per-account-overridable
  `reconciliation_error_threshold_kcal` (default `300` kcal/day) threshold
  ("recalibrate") -- both flag via the existing persisted/dismissible
  `GET /api/alerts`, never block, same pattern as every other detector.
- The Dashboard gained two charts (ingested-vs-tissue surplus;
  actual-vs-goal weekly increment, reusing `drawMultiLineChart`) and stat
  tiles for the rolling reconciliation error and the average weekly
  increment/deviation. The Settings view's "Body-fat & BMR calibration"
  section gained the new reconciliation-error-threshold field.

### Phase 3.3 — Wave 2: daily and weekly logs coexist (done)

Source: `docs/JustFitting_Oleada2_Sergio.pdf` (F6), generalized beyond
what the source doc specifies. The natural foundation for the Phase 2.1
"automatic steps import" idea:

- A log row gets a `granularity = daily | weekly` tag (`body_logs`,
  migration 15, default `'weekly'`, CHECK-constrained like the existing
  `source = real | projected` tag) instead of a separate daily-entry
  table that only exists to feed a forced weekly rollup. `POST`/`PUT
  /api/logs` accept it (default `weekly`); the log wizard's first step
  gained a Weekly/Daily selector, and the log table a Granularity badge
  column. Every week can be logged either way, and even mix over an
  account's history.
- A new pure module, `services/LogResampler.py`
  (`resample_to_weekly`), resolves a **weekly view** of mixed-granularity
  history: only `granularity="daily"` rows are ever grouped (by ISO
  calendar week), collapsing into one representative row — median
  weight (robust to a day's water/sodium swing), mean steps/cardio/
  waist/neck/intake, and `intake_is_real` true only if every grouped
  day's intake was real. `granularity="weekly"` rows (the default, and
  every log that existed before this phase) always pass through
  unchanged, regardless of weekday or spacing — grouping by calendar
  week regardless of tag was rejected as a real regression risk for
  accounts that don't log on a fixed weekday. `MetricsSeriesService.
  compute_series_for_user` calls the resampler once, so every existing
  consumer (`/api/metrics/*`, `/api/alerts`, adherence) keeps its 1:1
  logs/results assumption with no further changes; `GET /api/logs`
  still lists every raw row. The representative row for a resampled
  week is its max-date member's own real `log_id`, so the per-log
  `metrics_snapshots` cache needed no schema change.
- The symmetric **daily view** (`LogResampler.daily_view`) — a weekly
  log's values copy-pasted across every day since the previous one, the
  same "hold the last known value" idea `activity_model="constant"`
  already uses going forward, just applied backward across days a
  single log covers — is implemented and unit-tested but not yet wired
  to a route or UI, since nothing in the app has a per-day display today.
- An account that only ever logs weekly sees no change in behavior
  whatsoever (proven by the full pre-existing test suite staying green
  untouched).

### Phase 3.4 — Wave 2: TEF by macronutrients (done) — Phase 3 complete

Source: `docs/JustFitting_TEF_Macronutrientes.pdf` (F9). The single
biggest precision upgrade in Wave 2's energy model — landed last in the
sequence because it needs Phase 3.3's daily granularity to have somewhere
to read macros from, not because it's minor. **With this phase, F1–F9 are
all implemented — Phase 3 (Wave 2) is complete**, with nothing left
unscheduled from either source document's eight-plus-one capabilities:

- Optional `carbs_g`/`fat_g`/`protein_g` grams on any logged row
  (migration 16, nullable, no new table — three more fields on the same
  `BodyLog` row Phase 3.3 introduced), logged together or not at all
  (`CompositionEngine.validate_log_input` 400s a partial trio). A new
  `services/composition/Tef.py` computes the directly-summed weekly TEF
  (`kappa_carbs*carbs_g + kappa_fat*fat_g + kappa_protein*protein_g`),
  replacing the flat 10% guess additively (`TDEE = BMR+NEAT+EAT+TEF`,
  no divisor) whenever `EngineConstants.tef_mode="macros"` **and** that
  week has macros logged — protein costs far more to digest than carbs
  or fat (its `kappa_protein` coefficient is over 3x carbs' and 16x
  fat's), so two accounts eating the same calories with different macro
  splits get genuinely different, not identical, energy estimates,
  materially relevant for a high-protein bulk. A week with no macros
  logged falls back to the flat estimate automatically, regardless of
  the account's preferred mode — additive, never blocking.
  `LogResampler.resample_to_weekly` extends its mean-of-logged-days
  convention to the three macro fields, which works cleanly because TEF
  is linear in each one (the mean of daily TEF values equals the TEF of
  the mean macros).
- `CompositionResult` gained `tef_kcal`/`tef_mode` (which formula this
  row actually applied), bumping `CompositionEngine.ENGINE_VERSION`
  `1 -> 2` — the **first** version bump since the engine shipped, since
  this is a genuine compute-chain branch, not a read-side view like
  Phase 3.1–3.3's additions. Every log with no macros logged computes
  byte-for-byte identically to before regardless of the bump. `GET
  /api/metrics/tef` (new `Tef.compute_tef_breakdown`) breaks a week down
  by macro, showing the flat estimate alongside the macro figure for
  comparison; the Dashboard gained a "TEF (this week)" stat tile and a
  flat-vs-macros line chart.
- `tef_mode` (`"flat"` default | `"macros"`) is **account-level only**
  (`EngineConstants`/`EngineSettings`, historized, migration 17,
  alongside `kappa_carbs`/`kappa_fat`/`kappa_protein`, all
  per-account-overridable) — **not** a per-request query parameter,
  deliberately deviating from the source doc's "account setting +
  optional per-request override" wording. The same reasoning Phase 3's
  `bmr_model` already established applies: which TEF formula applies
  changes every metrics computation for an account, not just an
  ephemeral forecast, so it belongs on the same historized settings
  object as everything else, not a request-scoped override. The Settings
  view gained a "TEF by macronutrients" section; the log wizard's
  "Energy" step gained optional Carbs/Fat/Protein fields, and the log
  table/review step show them.
- A new `macro_kcal_mismatch` alert (`services/composition/Alerts.py`)
  flags — never blocks — a week whose declared `intake_kcal` diverges
  from what its logged macros imply (`4*carbs_g + 9*fat_g + 4*protein_g`,
  standard Atwater conversion) by more than `macro_kcal_mismatch_pct`
  (new, per-account-overridable, default 15%) — the source doc's own
  suggested soft coherence check, actually implemented rather than left
  as a suggestion.
- **Extension beyond either source PDF, shipped in the same phase**:
  evidence-based protein/fat intake targets by body mass. Commonly-cited
  sports-nutrition ranges are roughly 1.6–2.2 g/kg protein and 0.5–0.8
  g/kg fat for a cut, and 1.5–2.0 g/kg protein and 0.7–1.0 g/kg fat for a
  bulk; new `protein_target_g_per_kg`/`fat_target_g_per_kg`
  `EngineConstants`/`EngineSettings` fields (migration 19, defaulting to
  `1.75`/`0.70`, a mid-point inside both ranges, tunable per account)
  drive a new pure module, `services/composition/MacroTargets.py`
  (`compute_macro_targets`) — carbs are always the remainder of
  `target_calories` once protein/fat's kcal share is subtracted, never
  an independent target. Exposed via `GET /api/metrics/macro-targets`
  (target split plus the actual logged split, when available); two new
  alerts, `protein_target_deviation`/`fat_target_deviation`
  (`macro_target_deviation_pct`, default 20%), flag a logged week's
  grams diverging from target, only when macros are actually logged
  that week. The Dashboard gained a target-vs-actual stacked-bar chart
  (`drawMacroSplitBars`, a new `charts.js` primitive) comparing the two
  calorie splits by macro — a stacked bar rather than a pie/donut chart,
  per this project's dataviz guidance (part-to-whole comparison reads
  more reliably as adjacent bars than as angle judgments between slices).
  The Settings view gained a "Macro targets" section.
- New/extended test coverage: `Tef_test.py`, `MacroTargets_test.py`
  (new files), `CompositionEngine_test.py` (macro-mode TEF switching,
  the flat fallback, partial/negative-macro rejection),
  `LogResampler_test.py` (macro averaging, including the "no day logged
  it" case), `Alerts_test.py` (`MacroKcalMismatchAlertTest`,
  `MacroTargetDeviationAlertTest`), `EngineSettingsManager_test.py`
  (bounds/validation for every new field), and `Api_test.py` (macro
  round-trip on logs, both new endpoints' 404s and happy paths, the new
  settings fields' round-trip) — every pre-existing test stays green,
  proving an account that never logs macros is completely unaffected.
- `sw.js`'s `CACHE_NAME` bumped (`-v9` -> `-v10`) for the wizard/
  Settings/Dashboard UI changes.
- **Report and export now include every Wave 2 read-side view**,
  closing the "Future work" gap this same README section used to note:
  `GET /api/users/me/report` and `/export` both gained `gain_quality`,
  `energy_balance`, `increment_analytics`, `tef` and `macro_targets`
  sections (a shared `_wave2_metrics` helper in `user_routes.py`,
  reusing the exact `services/composition/*` modules and DTOs
  `GET /api/metrics/*` already exposes -- no new computation). The
  printable Report view gained five matching tables, so a bulk
  account's trainer/nutritionist export finally shows "is this bulk
  clean," "is the energy model tracking reality," and "is intake
  hitting its macro targets" at a glance. `/export`'s existing `logs`/
  `profile`/`goal_history`/`audit_log` fields (the actual import/restore
  contract) are unchanged; the new sections are additional, read-only,
  recomputed-not-restored data.

### Phase 4 — UX refinement: beta-testing feedback (done)

Source: `things-to-improve.txt`, Danel's own notes from the first round of
beta-testing the shipped v1.0.0 app. Five items, roughly in the order
they unlock each other (2-5 lean on 1, and on each other); this phase's
sub-phases track them 1:1. **All five, Phase 4.1-4.5, are done.**

#### Phase 4.1 — Consolidated top navigation (hamburger menu) (done)

Problem: the top bar packed eight destinations (Dashboard, Log,
Projection, Plan, Alerts, Report, Settings, Account) plus Logout into one
non-wrapping flex row, which crowded/overflowed on narrow viewports --
the primary width for the Android app -- and was already visually busy
on desktop. No responsive/mobile nav pattern existed before this phase.

- The always-visible `.nav-link` row is replaced by a single hamburger
  icon button (`#nav-toggle`, inline SVG, no icon-font/library
  dependency) that toggles a `.nav-menu` panel (`index.html`) listing the
  same eight destinations plus Logout, at every viewport width (not just
  behind a mobile breakpoint -- the "too many tabs" complaint called out
  the always-visible row itself). The eight destinations stay a flat
  list, no sub-grouping.
- The panel's items are the exact same `button.nav-link
  data-view="..."` elements `views.js`'s `showView()` already
  selects/highlights, so `showView`'s dual view-toggle/highlight
  responsibility needed no changes at all.
- `app.js` gained open/close state (`openNavMenu`/`closeNavMenu`), wired
  to the toggle's click, close-on-item-click (alongside the existing
  `navigate(view)` call), close-on-outside-click, and close-on-`Escape`
  (returning focus to the toggle); `showAuthOnly`/`enterApp`'s existing
  mass show/hide of nav elements on login/logout now covers the toggle
  button too.
- Accessibility: `aria-expanded`/`aria-controls` on the toggle,
  `role="menu"`/`"menuitem"` on the panel/items, `aria-label="Menu"`,
  Enter/Space/Escape all work, focus returns to the toggle on close.
- **A real bug caught only by manually screenshotting the running app**
  (not by the automated tests, initially): `.nav-menu { display: flex }`
  (an author-stylesheet rule) silently overrode the browser's default
  `[hidden] { display: none }` (a user-agent-stylesheet rule) regardless
  of specificity, since author rules beat user-agent rules in the
  cascade for any tie -- so the menu rendered open even while its
  `hidden` attribute was set. Fixed with an explicit `.nav-menu[hidden]
  { display: none }` rule. The Playwright test suite's own `_hidden()`
  helper had the same blind spot (it checked the `.hidden` IDL property,
  which only reflects the attribute, not actual rendering) and was
  rewritten to check `page.is_visible()` instead, so this class of bug
  fails the suite next time.
- `sw.js`'s `CACHE_NAME` bumped `-v10` -> `-v11` per this project's
  established convention, since `index.html`/`style.css`/`app.js` all
  changed.
- New Playwright coverage: `client/test/browser/Nav_test.py`, driving the
  real `client.src.Client.create_client_app` against a real API server
  (unlike `Views_test.py`'s minimal fixture harness, which doesn't
  include the topbar at all) -- open/close via the toggle, item-click
  navigation + active-highlighting + auto-close, Escape, outside-click,
  and logout all covered.
- Purely client-side: no server/API/DB changes, no `ENGINE_VERSION`
  implications, no `manifest.json` changes.

#### Phase 4.2 — Simplified dashboard-as-home summary (done)

`things-to-improve.txt` item 2: land on a simpler dashboard summary
first -- a last-logged weight/body-fat/lean-mass-and-change section, a
calories section, and a goal section (achieved vs. target, projected
weeks-to-complete) -- rather than today's full chart grid as the
landing view. A client-only change: every figure the new summary needs
was already computed and exposed by existing endpoints (`GET
/api/metrics/latest`'s `MetricsDTO` -- `body_fat`, `fat_mass_kg`,
`lean_mass_kg`, `weight_delta_kg`, `tdee`, `target_calories`,
`weight_to_shed_kg`, `weeks_to_goal`; `GET /api/metrics/gain-quality`'s
`delta_lean_kg`; `GET /api/users/me`'s `target_bf`/`direction`), so no
engine work, migration, or `ENGINE_VERSION` bump was needed.

- `#view-dashboard` (`index.html`) splits into an always-visible
  summary -- three `.stat-row` card sections (Weight & Body
  Composition, Calories, Goal) fed by a small, cheap fetch set -- and a
  `<details id="dashboard-details">`-collapsed "Full charts & advanced
  stats" section holding the existing 12-chart grid, collapsed by
  default and lazy-loaded only on first expand rather than fetched on
  every dashboard load. A custom `▸`/`▾` marker and a top border
  (`style.css`) replace the bare browser-default disclosure triangle so
  the section reads as clickable rather than a plain heading.
- `client/src/webapp/static/js/app.js`'s `refreshDashboard()` split
  into `refreshDashboardSummary()` (the new default on
  `navigate("dashboard")`: `metricsLatest`, `metricsSeries`,
  `gainQuality`, `adherence`, `alerts`) and `refreshDashboardCharts()`
  (`listLogs`, `goals`, `energyBalance`, `incrementAnalytics`, `tef`,
  `macroTargets`, reusing the series/gain-quality already fetched by
  the summary via `state`), the latter wired to the `<details>`
  element's `toggle` event and guarded (`state.dashboardChartsLoaded`)
  so it runs at most once per login session; `enterApp()` resets that
  flag and re-collapses the section on every fresh login so a second
  account's charts are never shown stale.
- `views.js` gains `renderWeightSummary`, `renderCaloriesSummary`,
  `renderGoalSummary`, and shared `formatDelta`/`statTile` helpers
  (▲/▼/– plus the signed value, in a neutral/muted color rather than
  red/green -- "good" direction depends on the account's cut/bulk
  `direction` and differs per metric, so that judgment is deliberately
  left for later rather than guessed at now). `renderDashboardStats`
  (the collapsed section's tile row) now only surfaces the genuinely
  *advanced* figures -- TEF, cumulative fat ratio, energy-balance
  error, average weekly increment, deviation from goal rate -- since
  Weight/Body fat/Lean mass/To-target/Weeks-to-goal/Adherence are all
  covered by the new summary sections and would otherwise be shown
  twice. Its badge-bearing tiles (TEF, cumulative fat ratio,
  energy-balance error, avg weekly increment) originally wrapped their
  entire value in a small `.badge` pill or crammed a goal figure onto
  the same line, which read inconsistently against every plain
  `statTile`; every tile's number now stays in the same big/bold
  `.value` style, with ideal/threshold/goal context moved into a small
  subtitle underneath (the same neutral `.delta` line style the
  summary sections' "target"/"goal" subtitles already use). Only TEF's
  mode tag ("flat"/"macros", a label rather than a good/bad judgment)
  keeps a colored `badgeDelta()` pill; cumulative fat ratio's "ideal"
  and energy-balance error's "threshold" subtitles are now plain,
  uncolored text like every other subtitle.
- New browser test coverage, `client/test/browser/Dashboard_test.py`
  (no dashboard-specific browser test existed before this phase --
  `Nav_test.py` only checks the view is shown): the three summary
  sections render expected values (including a change indicator once a
  second week is logged), a brand-new account with no logs gets a
  friendly placeholder instead of an error, `#dashboard-details` starts
  closed with chart SVGs empty until expanded, and expanding it draws
  the charts.
- `sw.js`'s `CACHE_NAME` bumped (`-v11` -> `-v12`) per this project's
  established convention.
- Manually verified against both seeded demo accounts
  (`scripts/seed_demo_data.sh`): `admin_cut`'s summary reproduces the
  README's own Danel worked example almost exactly (BF 19.9%, TDEE 2583
  kcal, target 2027 kcal, ~11.9 weeks to goal); `admin_bulk` renders the
  same layout correctly with upward weight/lean-mass deltas and a
  "Bulk" direction badge.
- No server/API/DB changes.

#### Phase 4.3 — Projected-weeks toggle on Dashboard charts (done)

`things-to-improve.txt` item 3: a toggle on the Dashboard's charts to
overlay the forecast alongside real data, with a dashed vertical line
marking the last logged day, so the user sees "the next N weeks"
directly on the chart they're already looking at instead of switching to
the separate Projection view.

**Scope**: the toggle affects the five line/multi-line charts inside
`#dashboard-details` that have a real "future" to extrapolate — Weight,
Body fat %, Target calories, Waist/Neck (perimeters), and Goal
trajectory. It does **not** touch Steps (a flat continuation under the
default constant-activity forecast has little visual value) or the two
bar charts (Fat/lean mass stack, Gain-quality diverging bars), since bar
marks don't have as clean an "append future bars past a marker line"
convention as a continuous line does — left for a later pass if it turns
out to be wanted.

- **Server** (`server/src/api/projection_routes.py`): `GET
  /api/projection` today returns `MetricsDTO` rows only, which cover
  weight (derived as `fat_mass_kg + lean_mass_kg`), body fat %, and
  target calories, but not the forecasted waist/neck themselves — those
  only exist on the `LogInput` half of
  `Projection.project_series_with_inputs`'s return pairs, currently
  surfaced only by the persisting `POST /api/projection` via
  `ProjectionDTO`. The `GET` route switches from `project_series` to
  `project_series_with_inputs` and adds three keys to each returned row
  — `estimated_weight`, `estimated_waist`, `estimated_neck` (the same
  names `ProjectionDTO` already uses for the same values) — alongside
  the existing `MetricsDTO` fields. Purely additive: every existing
  field keeps its exact meaning and value, so the standalone Projection
  view (`renderProjectionTable`, which only reads
  `fat_mass_kg`/`lean_mass_kg`/`body_fat`/`target_calories`) needs no
  change. No migration, no `ENGINE_VERSION` bump — this is a read-side
  response-shape change, not a compute-chain change.
- **Client — `charts.js`**: `drawMultiLineChart` already supports a
  `markers` option (a dashed vertical line with a hover title, used
  today for goal-plan-change markers on the goal-trajectory chart), but
  `drawLineChart` (the single-line Weight/Body fat/Calories charts) has
  no equivalent. The marker-drawing block is extracted into a shared
  `drawMarkerLines(svg, markers, xScale, width, height)` helper used by
  both, and `drawLineChart` gains the same `markers = []` option
  `drawMultiLineChart` already has.
- **Client — `index.html`**: a small control row — a checkbox ("Show
  next N weeks") plus a weeks `<select>` (4/8/12, default 4, matching
  the note's own "the next 4 weeks" phrasing) — is added inside
  `#dashboard-details`, after the advanced-stats tile row and before the
  chart grid it actually affects, so it's only ever interactive once the
  charts themselves are expanded/loaded (Phase 4.2's lazy-load guard
  already ensures that).
- **Client — `app.js`**: `refreshDashboardCharts()` splits into a
  data-fetch half (unchanged) and a pure `renderDashboardCharts()` draw
  half, so toggling the projection control doesn't refetch
  logs/goals/energy-balance/etc. — only the forecast itself. New state:
  `state.showProjection` (bool, default `false`) and
  `state.projectionWeeks` (default `4`), plus a small per-weeks-value
  cache (`state.projectionCache`) so flipping the toggle off and back
  on, or re-picking the same weeks value, doesn't re-hit the API. When
  the toggle is on:
  - `api.projection(weeks, "real", "constant")` is fetched (plain-OLS
    trend, real-only regression base, constant activity — the same
    defaults the standalone Projection view opens with) and its rows
    are appended to a *copy* of each affected chart's series, never
    mutating `state.series` itself, which the summary section and every
    other chart also read.
  - Every forecast row already computes with `intake_is_real=false` →
    `source="projected"` from the engine itself (the same field the
    existing "assumed intake" weeks already use), so the "(forecast)"
    tooltip suffix in `drawLineChart`/`drawMultiLineChart` applies to
    genuinely-future weeks with no new code needed. Point *markers* for a
    projected row are hollow (unfilled, stroked in the series' own color)
    instead of a real row's filled dot -- a shared `drawPointMarker`
    helper used by both chart functions, replacing an earlier
    inconsistent pass (a smaller dot in an unrelated red on
    `drawLineChart`, no distinction at all on `drawMultiLineChart`) that
    read as a jarring color swap rather than "this point isn't measured
    yet." The line itself stays one continuous color/style across the
    real-to-projected boundary; only the marker shape changes. The
    perimeters chart's waist/neck accessors fall back to the new
    `estimated_waist`/`estimated_neck` fields when `row.log_id` is
    `null` (true for every forecast row, never true for a real logged
    week).
  - Each affected chart gets a `markers: [{ date: <last real log's
    date>, label: "Last logged" }]` so the dashed line lands in the same
    place on every chart, independent of how many weeks are toggled on.
    The goal-trajectory chart's own pre-existing goal-plan-change markers
    (Phase 1.4) are filtered to `goal.start_date <= <last real log's
    date>` before merging in the forecast marker: a goal's `start_date`
    is the real wall-clock date it was created/changed (e.g. the very
    first goal, dated at registration), which can fall after the last
    logged week and previously just got silently clamped to the chart's
    right edge on the real-only date domain -- widening that domain via
    the forecast toggle would otherwise make it reappear mid-chart as a
    second, unrelated marker alongside "Last logged".
  - Turning the toggle off (or collapsing `<details>`) redraws every
    chart from the unmodified base series, discarding the appended rows
    — the forecast is never written anywhere, matching the read-only
    nature of `GET /api/projection` today.
- **Out of scope for this phase**: the "N weeks to goal" figure is
  already shown as text in the Phase 4.2 Goal summary card; this phase
  is only the chart overlay, not a new number. Configuring
  `base`/`activity`/`trend_model` from the Dashboard toggle (rather than
  the standalone Projection view) is also left out — the toggle is
  deliberately simpler than the full Projection view's controls, per the
  note's own "make it like the next 4 weeks" framing.
- **Testing**: `Api_test.py`'s existing `test_projection_endpoint` case
  gained an assertion that the three new fields round-trip correctly; two
  new cases in `client/test/browser/Dashboard_test.py`
  (`test_projection_toggle_overlays_forecast_and_marker`,
  `test_goal_trajectory_marker_excludes_a_future_dated_goal_change`)
  drive the toggle end-to-end against a real server+client — off by default,
  turning it on appends the expected number of forecast points (via the
  rendered SVG circle count) with the "Last logged" marker line present,
  a weeks-value change from 4 to 8 appends more, and turning the toggle
  back off removes them all.
- **Housekeeping**: `sw.js`'s `CACHE_NAME` bumped `-v12` -> `-v13` per
  this project's established convention, since `index.html`/`app.js`/
  `charts.js`/`style.css` all changed.

#### Phase 4.4 — Redesigned log capture (day/week view) (done)

`things-to-improve.txt` item 4: replace the Log view's current layout --
the wizard on top, then one unbounded table of every log the account has
ever created underneath -- with a calendar-style navigator (prev/next
arrows, a day/week toggle, a date picker) that puts the wizard "inside"
a chosen day, defaults to today, and shows only that day's (or that
week's) logs below it. The problem this solves: as an account
accumulates logs (especially daily-granularity ones, Phase 3.3), the log
table grows long and loses the "what did I log today" framing the note
asks for. A **client-only** change, like Phase 4.2/4.3 -- `GET
/api/logs` already returns every log for the account in one call, so
"day view" / "week view" is a client-side filter over data already
fetched, not a new endpoint. No migration, no `ENGINE_VERSION` bump, no
server route changes.

**Scope decisions**:

- **The wizard's Date field is replaced by a read-only label bound to the
  navigator's selected day**, instead of staying a freely-editable date
  input. This is the literal reading of "the log is done inside that
  day" -- you pick the day via the navigator first, then the wizard logs
  *for* that day, rather than picking a day twice (once in the
  navigator, once again in the wizard). The actual submitted value is
  unchanged: a hidden `<input type="hidden" name="date">` keeps
  `formToJson()`'s existing read working with no changes to the submit
  handler; only the visible UI moves from an editable input to a display
  label + the navigator controls. Hidden inputs are exempt from HTML
  constraint validation, so `currentLogStepIsValid()`'s existing
  `reportValidity()` loop over step 1's inputs needs no special-casing.
- **"Week" means the ISO calendar week (Monday-Sunday)** containing the
  selected day -- the same grouping `LogResampler.resample_to_weekly`
  already uses server-side for daily-tagged rows (README's Phase 3.3), so
  "week view" shows exactly the days the engine itself would fold
  together, not an arbitrary rolling 7-day window.
- **The granularity `<select>`'s default follows the view mode** (`daily`
  in day view, `weekly` in week view) as a convenience -- day view is
  where per-day logging naturally happens, matching the note's own
  framing -- but it stays a manual override otherwise; nothing forces a
  value. Easy to drop if this reads as more surprising than helpful.
- **No inline edit UI is added.** Today the Log view only supports
  create + delete (`update_log` exists server-side but has no client
  form); that stays true here. Not asked for by the note, and the
  smaller filtered list doesn't itself require it.
- **No pagination or new date-range API.** `state.logs` already holds
  every log for the account after one `GET /api/logs` call (Phase 4.2
  established this is cheap enough not to worry about -- a personal
  weekly tracker tops out at a few hundred rows even after years); the
  navigator only changes which subset of the already-fetched array is
  rendered.
- **The old "every log ever" table is retired, not relocated.** Full
  history stays reachable via the date-picker (jump straight to any past
  date), the Report view's full weekly series table, and the JSON Export
  button -- not a data-loss concern.

**Client — `index.html`** (`#view-log`): a new `.log-nav` control row
above the existing `<form id="log-form">`:

- `‹`/`›` arrow buttons (`#log-nav-prev`/`#log-nav-next`) flanking a
  label (`#log-nav-label`) -- "Today" / a weekday-and-date string in day
  view, "Week of `<Mon>` - `<Sun>`" in week view, with `‹`/`›` stepping by
  1 day or 7 days depending on the active mode.
- A two-button Day/Week toggle (`#log-nav-day`/`#log-nav-week`, styled
  like the existing `.nav-link.active` pattern) instead of a `<select>`,
  since there are only ever two states.
- A date-picker (`#log-nav-date`, `<input type="date">`) to jump directly
  to any date; in week view it jumps to the ISO week containing the
  picked date.
- Step 1 of the wizard drops its visible `date` input for a `<p>` reading
  "Logging for **`<selected day>`**" plus the hidden date field described
  above.
- Below the wizard, the log table's heading becomes dynamic
  (`#log-list-heading`: "Today's logs" / "This week's logs" / "Logs for
  `<date>`" once the user has navigated away from today), and the table
  itself only ever renders the filtered subset -- with a
  `<p class="disclaimer">` placeholder ("No logs for this day/week yet.")
  when that subset is empty, the same empty-state pattern Phase 4.2's
  summary sections already use.

**Client — `app.js`**: new state, `logNav: { selectedDate: <today's ISO
date>, viewMode: "day" | "week" }`, reset to today/day-view alongside the
other per-login state `enterApp()` already resets (dashboard flags,
projection toggle) so a second account never inherits the first one's
place in its log history.

- `refreshLogs()` keeps fetching the full `state.logs` array unchanged,
  then calls two new pure-render helpers: `renderLogNav()` (label,
  date-picker value, active toggle button, the wizard's hidden date field
  and display label) and `renderFilteredLogList()` (computes the day/week
  subset of `state.logs` and calls the existing `renderLogTable` plus the
  new heading/placeholder logic).
- A small pure helper, `isoWeekRange(dateStr)`, returns the
  Monday/Sunday bounds for a date -- used both for the week-view label
  and the week-view filter -- mirroring the same ISO-week convention
  `LogResampler` uses server-side, kept client-side since it's pure date
  math with no fetch involved (consistent with `formToJson`, an existing
  pure helper already living in `app.js`, not `views.js`).
- New DOM listeners for the prev/next arrows, the two toggle buttons, and
  the date-picker's `change` event, all routed through one
  `setLogNav(patch)` that merges into `state.logNav` and re-renders the
  nav + filtered list from the already-fetched `state.logs` -- no
  re-fetch, matching Phase 4.3's "toggling a control shouldn't refetch
  everything" precedent.
- The log-submit handler's existing `await refreshLogs()` call is
  unchanged; since the submitted date always comes from
  `state.logNav.selectedDate`, a newly-created log always lands inside
  the currently-viewed day/week and appears immediately.

**Client — `views.js`**: `renderLogTable` itself is unchanged -- it's
still handed a plain array of logs, just a filtered one now instead of
all of them, and an empty array already renders an empty `tbody`.
`app.js`'s `renderFilteredLogList()` toggles `#log-table`/`#log-list-empty`'s
`hidden` attributes based on the filtered count, rather than teaching
`renderLogTable` a new empty-state branch.

**Client — `style.css`**: a `.log-nav` flex row (arrows + label + toggle
+ date-picker) styled consistently with the existing `.inline-form` /
`.nav-link.active` patterns -- no new visual language introduced.

**Testing**: a new `client/test/browser/Log_test.py` (no log-view-specific
browser test existed before this phase -- `Views_test.py` only checks the
minimal fixture harness, `Api_test.py` covers the HTTP layer): default
day view opens on today with an empty-state placeholder on a fresh
account; saving a log through the wizard lands it in the
currently-selected day and appears in the filtered list immediately; the
prev/next arrows move the selected day and update both the label and the
filtered list; switching to week view groups two logs from the same ISO
week together while day view shows only one at a time. `Dashboard_test.py`'s
own `_log_week` helper, which used to `fill()` the wizard's date input
directly, now drives the new `#log-nav-date` date-picker instead, since
that input is hidden.

**Housekeeping**: `sw.js`'s `CACHE_NAME` bumped `-v13` -> `-v14`, since
`index.html`/`app.js`/`style.css` all changed.

#### Phase 4.5 — Retire the standalone Projection view (done) — Phase 4 complete

`things-to-improve.txt` item 5: now that 4.3 (Dashboard forecast toggle)
and 4.4 (Log view day/week navigator) have both shipped, the dedicated
Projection view/tab is removed entirely -- forecast data becomes a toggle
on the Dashboard (already true since 4.3) and appears directly in the Log
view as a tagged row, rather than its own nav destination. **Client-only**,
like every other Phase 4 sub-phase: `GET /api/projection` already returns
everything needed (Phase 4.3 added `estimated_waist`/`estimated_neck`), so
this is removing UI and reusing an existing fetch, not new server work --
no migration, no `ENGINE_VERSION` bump.

**Remove**:

- The `data-view="projection"` nav button (`index.html`), the
  `#view-projection` section (weeks/base/activity controls +
  `#projection-table`), and `navigate()`'s `if (viewName ===
  "projection")` branch (`app.js`).
- `refreshProjection()`/`renderProjectionTable()` (`app.js`/`views.js`)
  and the `#projection-refresh` click listener.
- `Client_test.py`'s markup assertion on `id="projection-activity"` (the
  only test that touches the standalone view; `Dashboard_test.py`'s own
  projection-toggle tests exercise `#dashboard-projection-toggle`, not the
  standalone view, and are unaffected).

**Add -- a projected row directly in the Log table**, gated by a
**Settings-view preference** rather than a per-view toggle:

- **The preference lives in Settings, not the Log view, and persists in
  `localStorage`, not the server -- defaulting on.** A checkbox
  (`#settings-show-projected-logs`, "Show projected values on future
  dates") sits in its own "Log view" section, above and clearly separated
  from the historized `#settings-form` (its own disclaimer says so
  explicitly): it's a pure display preference, not an engine input, so
  historizing it alongside TEF/BMR calibration would be a category error
  -- `session.js` gained `getShowProjectedLogs()`/`setShowProjectedLogs()`
  (a `justfitting.showProjectedLogs` key, same pattern as the existing
  token storage) instead of a new `EngineSettings` field/migration.
  `getShowProjectedLogs()` treats an unset key as `true`, so a first-time
  user sees projected rows without having to find the checkbox first;
  once explicitly turned off it stays off, persisting across sessions on
  the same browser unlike the Dashboard's own forecast toggle (which
  always resets to off on login).
- **When it's on** and the navigator's selected day (day view) or week
  (week view) has no logged row yet and falls after the last *real*
  logged date (`state.logs` filtered to `source === "real"`, not a
  previously-saved projected run), `refreshProjectedRow()` (`app.js`)
  fetches the forecast and injects one synthetic row straight into
  `#log-table` via `renderLogTable` (`views.js`) -- the **same columns**
  a real log uses, not a separate widget. `renderLogTable` now accepts a
  `log_id: null` row: it renders with no `data-log-id`, no Delete button
  (nothing persisted to delete), a `log-row-projected` CSS class (italic,
  muted text -- a visual cue beyond the badge alone), and its `source`
  badge reads "projected" using the exact same `.badge.projected` style a
  persisted-but-not-real log already used. Fields the forecast never
  observed -- intake, steps, cardio, macros -- are `null` and render as
  "--" (a new `dash()` helper) rather than fabricated; weight, waist, and
  neck come from the projection row's
  `estimated_weight`/`estimated_waist`/`estimated_neck`, always shown to
  exactly 1 decimal (a new `round1()` helper using `toFixed(1)`, not plain
  rounding, so a whole-number estimate still reads "88.0", not "88").
- **The forecast stays weekly, never fabricated per-day.** The engine
  forecasts one row per week (Phase 4.3); day view doesn't invent a daily
  figure for a day that isn't itself a forecasted row -- it shows the
  forecasted week *covering* the selected day (the row whose date falls
  in that day's ISO week, same Monday-Sunday convention
  `LogResampler`/Phase 4.4's week view already use). Its Granularity
  column always reads "weekly" (the existing `.badge.weekly` style) for
  the same reason -- never "daily", regardless of which Log-view mode is
  active when it's shown.
- **Weeks-ahead is derived from navigation, not a separate input**: unlike
  the old standalone view's free-typed "Weeks" field, there's no control
  of its own -- how far to forecast is just "however far the user has
  navigated," computed as `ceil(days between last real log and the
  selected day/week-end / 7)`, clamped to at least 1 and at most 52 (the
  same upper bound the old view's input enforced). Fixed at the
  Dashboard toggle's own defaults, `base="real"`, `activity="constant"`
  -- configuring those was already out of scope as of Phase 4.3 and stays
  that way; removing the standalone view means that configurability is
  gone entirely, an accepted trade-off for the simplification the note
  asks for, not an oversight.
- **`app.js`'s existing `getProjectionRows()`/`state.projectionCache`
  (Phase 4.3) is generalized into a plain `fetchProjectionWeeks(weeks)`
  helper**, cached per weeks value exactly as before, called by both the
  Dashboard's forecast toggle and the Log view's row injection -- since
  both request the identical `(weeks, "real", "constant")` series, they
  share one cache/one fetch instead of hitting the API twice for the same
  weeks value in the same session.
- Injecting the row is a small async step (`refreshProjectedRow()`) kept
  separate from the existing synchronous `renderFilteredLogList()` (which
  keeps instantly re-filtering `state.logs` on every nav click, same as
  Phase 4.4; it now optionally takes an extra row to append) -- called
  after `setLogNav()`/`refreshLogs()`/the Log view's own Day/Week toggle
  buttons, same "don't block the snappy nav re-render on a network call"
  precedent Phase 4.3 set for the Dashboard's own toggle. It also guards
  against a slow response landing after the user has already navigated
  elsewhere, re-checking `state.logNav` before rendering.
- **Out of scope**: no "log this now" shortcut that pre-fills the wizard
  from the projected row (a different note, `things-to-improve.txt`'s
  Phase 5 beta-testing item 4, covers wizard defaults generally); no
  change to what dates the wizard itself will accept -- creating a real
  log against a future date was already possible before this phase and
  isn't newly restricted or newly encouraged by the projected row.

**Testing**: two new `Log_test.py` cases -- logging two real weeks, then
turning the Settings preference on and jumping to a day two weeks past
the last one injects a row tagged "projected" with no Delete button (and
keeps `#log-table` visible instead of the empty-state placeholder), and
turning the preference back off removes it in favor of the normal empty
state; a second case confirms navigating back to a day that already has
a real log shows only that one row (tagged "real", with its Delete
button intact), even with the preference on. `Client_test.py`'s check for
the removed standalone view's markup now also asserts
`#settings-show-projected-logs` exists.

**Housekeeping**: `sw.js`'s `CACHE_NAME` bumped `-v14` -> `-v15`
(`index.html`/`app.js`/`views.js`/`style.css`/`session.js` all change).

**With this phase, Phase 4 (UX refinement: beta-testing feedback) is
complete** -- all five `things-to-improve.txt` items from the first round
of beta-testing are shipped.

### Phase 5 — Beta-testing feedback, round 2 (in progress)

Source: `things-to-improve.txt`'s "Things to change (Beta-testing) Phase 5"
section, Danel's second round of beta-testing notes -- eight items, mostly
independent of each other (unlike Phase 4's chained items). Sub-phases
below track them 1:1 in the order the note lists them.

#### Phase 5.1 — Self-versioning service-worker cache (done)

Problem: every prior phase's Housekeeping note ends with a manually-bumped
`sw.js` `CACHE_NAME` (`-v9` -> `-v10`, ... -> `-v15` so far) -- easy to
forget, and it's pure busywork a machine can do itself.

- `sw.js` computes its own cache name at runtime instead of using a literal:
  it fetches every `APP_SHELL` file fresh (`cache: "no-store"`), hashes
  their concatenated bytes with `crypto.subtle.digest("SHA-256", ...)`, and
  uses the first ~16 hex chars, prefixed `justfitting-shell-`, as the cache
  name. `install` fetches+hashes+populates the freshly-named cache in one
  pass (no double-fetch: the same `Response` object used for hashing is
  the one `cache.put()` stores); `activate` re-fetches+re-hashes to know
  "today's" name and deletes every *other* `justfitting-shell-*` cache; the
  `fetch` handler's stale-while-revalidate write-back looks up the current
  cache name via a cheap `caches.keys()` scan (no re-hash) rather than a
  hardcoded constant.
- Any future edit to any shell file changes the hash automatically ->
  automatically a new cache -> the old one purged on the next `activate`.
  **Zero manual version bumps, ever, going forward** -- this is the last
  phase whose Housekeeping note will ever say "CACHE_NAME bumped".
- No build-script or Android-packaging changes -- purely inside `sw.js`,
  so it works identically for the local dev server, the GitHub Pages
  static build, and the Android-bundled `dist/`.
- Trade-off: `install`/`activate` each do one extra fetch+hash pass over
  the (small, handful-of-KB) app shell -- negligible, and only happens
  once per service-worker lifecycle event, never per page load or
  network request.
- **Testing**: this repo has no existing service-worker test infrastructure
  (Playwright's page-level tests don't inspect `caches`/SW lifecycle), and
  standing one up is disproportionate to a single small file -- covered by
  manual verification instead (DevTools Application tab: cache name changes
  after editing a shell file; the old cache is gone after the next reload),
  called out explicitly rather than silently skipped.
- **Verified**: a Playwright-driven manual check (register, log two weeks,
  inspect `caches.keys()`) confirmed the installed cache name is a computed
  hash (e.g. `justfitting-shell-202229d05c7f371f`), not a `-vN` literal, and
  that the service worker activates normally.

#### Phase 5.2 — Registration no longer asks for a goal; sane per-sex defaults (done)

Problem: `POST /api/users` requires `target_bf`/`weekly_rate` and creates a
goal plan immediately at registration. The note wants account creation
decoupled from goal-setting entirely: a new account should start from a
harmless default (15% BF male / 22% female, 0% weekly rate = "no change
yet"), with the user visiting the Goal (Plan) section only once they
actually want to set a real goal.

- New constants (`services/composition/constants.py`):
  `DEFAULT_TARGET_BF_MALE = 0.15`, `DEFAULT_TARGET_BF_FEMALE = 0.22`,
  `DEFAULT_WEEKLY_RATE = 0.0`.
- `UserManager.register()`'s `target_bf`/`weekly_rate` parameters become
  optional (default `None`); when omitted, they're resolved from the new
  constants by `sex` before calling `create_goal_plan` -- a goal plan is
  still always created (the engine has no "no goal" mode and isn't
  getting one here; every account still needs *a* goal to compute
  anything against), it's just invisibly defaulted rather than
  user-chosen at signup.
- `POST /api/users` (`user_routes.py`) drops `target_bf`/`weekly_rate`
  from its required payload keys.
- **Client**: the register form (`index.html`/`app.js`) drops the "Target
  body fat (%)"/"Weekly rate (%)" fields entirely -- registration becomes
  just username/email/password/height/sex/birthdate.
- "Has everything empty" (the note's phrase) is already true today for a
  fresh account with no logs (Phase 4.2's placeholders) -- this phase
  doesn't change that; it only stops *asking for a goal* at signup.
- Ties directly into Phase 5.8 below (goal editing lives only in the Plan
  tab from here on, for both new and existing accounts).
- **Testing**: server-side cases (`UserManager_test.py`/`Api_test.py`) for
  both sexes' defaults when `target_bf`/`weekly_rate` are omitted, and
  that explicitly passing them still works (nothing currently needs that,
  but nothing should break it either); browser coverage that the register
  form has no goal fields and registration succeeds without them.
- **Bug found during implementation**: `Trajectory.compute_weeks_to_goal`
  divides by `ln(1 - weekly_rate)`, which is exactly `0` at
  `weekly_rate = 0` -- a `ZeroDivisionError` the instant any log is
  computed for an account on the new default. Nothing validates
  `weekly_rate` today (only `target_bf` is range-checked), so this was
  already a latent, manually-triggerable bug; Phase 5.2 just makes it the
  default path. Fixed in `Trajectory.compute_weeks_to_goal` with the same
  `abs(weekly_rate) < 1e-9` epsilon guard `IncrementAnalytics.py` already
  uses for its own zero-rate case, returning `0.0` -- the same "no
  meaningful figure" sentinel already produced when `weight_kg ==
  final_weight_kg`, which every consumer already renders as "--".

#### Phase 5.3 — Scope computed series/charts/projections to the active goal's period

Problem: `MetricsSeriesService.compute_series_for_user` and the projection
routes always compute/fit over **every** real log the account has ever
made, applying only the **currently active** goal's `target_bf`/
`weekly_rate` uniformly across all of it (`GoalPlanManager.
build_profile_params` returns a single `ProfileParams`, not one per
historical period). So changing your goal (e.g. finishing a cut, starting
a bulk) silently recomputes every historical week's target/trajectory/
deficit as if the new goal had applied the whole time, and feeds
pre-change data into the forecast's trend regression -- "the issue in
projections and plotting tendencies" the note flags.

- Fix: `compute_series_for_user` filters logs to `date >=
  active_goal.start_date` before resampling/computing -- the engine only
  ever "sees" the current goal's own period. `projection_routes.py`'s
  `_forecast_inputs` gets the same filter for its regression source.
- For the common case (an account that's never changed its goal),
  `start_date` is at-or-before the first log, so this is a no-op -- only
  accounts that have actually changed goals are affected, and only for
  data predating the change.
- `GET /api/logs` (the raw log list -- Log view's table, `/export`) is
  **unaffected**, intentionally: full raw history stays reachable there,
  the same "not a data-loss concern" precedent Phase 4.4 established for
  the log table. Only the *derived* series (metrics, charts, alerts,
  adherence, projections, report) is scoped to the active period.
- **Consequence to flag explicitly**: the goal-trajectory chart's
  goal-change markers (Phase 1.4) become moot for any change before the
  current period, since that earlier data no longer appears on the chart
  at all -- at most one marker is ever visible from now on (the current
  goal's own start). Not a bug, a direct consequence of the fix; worth a
  one-line disclaimer on that chart if it reads as surprising in practice.
- **Alternative considered and rejected for now**: recomputing each
  historical row against whichever goal was *actually* active on its own
  date (true historized replay). More thorough, but a much bigger engine
  change (the whole "`ProfileParams` is one value per series" assumption
  would need to become per-row) for a fix the note's own wording ("only...
  the actual goal plan period") reads as asking for the simpler
  period-filter, not a full historical replay.
- **Testing**: a new/extended `MetricsSeriesService_test.py` case with a
  synthetic two-goal history, asserting logs before the goal change are
  excluded from the computed series; a matching `Projection_test.py`/
  `Api_test.py` case for the regression source; every existing
  single-goal-history test must stay green untouched (proving the
  no-op case for accounts that never change their goal).

#### Phase 5.4 — Log wizard defaults to the last log's perimeters (done)

Problem: the wizard always opens with blank Waist/Neck fields, even though
most weeks a person's perimeters barely change -- the note asks it to
start pre-filled from whatever was last logged.

- `refreshLogs()`'s existing "fresh wizard" reset points (entering the Log
  view, switching day/week, after a successful save -- the same points
  `resetWizardGranularityDefault()` already hooks) gain a sibling
  `prefillWizardFromLastLog()`: finds the most recent `source === "real"`
  log across the whole account (not scoped to the navigated day/week) and
  pre-fills `waist_cm`/`neck_cm` from it; leaves them blank for a
  brand-new account with no real logs yet. **Implementation note**: the
  "fresh wizard" reset is actually three call sites in `app.js`
  (`refreshLogs()` and both day/week toggle handlers), not one, so
  `resetWizardGranularityDefault()` and `prefillWizardFromLastLog()` are
  folded into one shared `resetWizardDefaults()` used at all three,
  rather than tripling the call.
- Scoped to perimeters only, per the note's own "at least in perimeters"
  -- weight is deliberately left blank (it's the one number that's
  supposed to change and get re-measured every time; defaulting it risks
  the user not noticing a stale value and mis-logging), and
  intake/steps/cardio/macros stay blank too (today's actual entry, not a
  carry-forward).
- A manual edit to the pre-filled value is naturally preserved (it's just
  a normal input's default value, not a rewritten one) until the next
  fresh-wizard reset point.
- **Testing**: a new `Log_test.py` case -- after saving a log with a given
  waist/neck, opening the wizard again (a nav change, or the next day)
  shows those same values pre-filled; a brand-new account's first-ever
  wizard still opens blank.

#### Phase 5.5 — Fix "Weight to goal" (was showing the weekly delta, not the total remaining) (done)

Problem (confirmed bug, reported as "always showing 0.5kg"): the Goal
summary's "Weight to goal" tile reads `Math.abs(latest.weight_to_shed_kg)`
-- but `weight_to_shed_kg` (`Pi`, `Trajectory.py`) is `prev_week_weight -
this_week's_objective`, i.e. **this week's** incremental target change
(`-prev_weight * weekly_rate`), which for a steady ~0.5%/week rate on a
~90-100kg body is *always* going to land around 0.45-0.5kg regardless of
how close the goal actually is -- exactly the symptom reported. It's the
wrong field for "how far am I from my goal" -- that's a *stock* (total
remaining distance), not the *flow* (this week's slice of it).

- Fix is client-only: `MetricsDTO` already carries `final_weight_kg`
  (`lean_mass_kg / (1 - target_bf)`, `Trajectory.compute_final_weight`'s
  own goal-weight figure) -- "Weight to goal" becomes `(latest.fat_mass_kg
  + latest.lean_mass_kg) - latest.final_weight_kg` (current total weight
  minus the goal weight), the actual total remaining distance, computed
  from fields the API already returns. No server change, no new endpoint.
- `weight_to_shed_kg` itself is untouched and stays correct for its actual
  job (driving `daily_deficit`/`target_calories` inside the engine) --
  only the Dashboard tile was wired to the wrong field.
- **Testing**: a `Dashboard_test.py` case asserting the "Weight to goal"
  tile shrinks week over week as logged weight approaches
  `final_weight_kg`, rather than staying flat at ~0.5kg across weeks.

#### Phase 5.6 — Clearer Calories summary: label what each figure means (done)

Problem: the note's own framing is the clearest problem statement --
"you'd expect target calories = how much you should eat, TDEE = how much
you did eat, and adherence = the daily difference, but it doesn't match":
TDEE is actually *estimated energy expenditure* (never intake), and
Adherence is the *mean* deviation of real intake from target *across every
real-intake week*, not a single day's arithmetic between the other two
tiles -- both true and correctly computed today, but presented as three
bare numbers with no explanation of what they are or how (if at all) they
relate to each other.

- `renderCaloriesSummary` (`views.js`) gains a subtitle line under each
  tile (a new, smaller `.delta.tile-subtitle` variant of the existing
  muted `.delta`-style convention Phase 4.2 established for
  "target"/"threshold" context -- kept intentionally terse rather than a
  full sentence): "Target calories" -> "what to eat"; "TDEE" ->
  "estimated calories burned"; "Adherence" -> "actual vs target/day"
  (its value itself drops the "/day" suffix, e.g. "-180 kcal", since the
  subtitle now carries that).
- Adds a fourth tile, **this week's logged intake** (the latest real
  log's `intake_kcal`, no new endpoint), placed directly before Adherence
  so the three genuinely comparable numbers (ate / should-eat / burn) sit
  next to each other, with Adherence (a derived comparison, not a raw
  figure) last. **Implementation note**: `intake_kcal` isn't actually
  pre-fetched at Dashboard-summary time (it only arrives via the
  lazy-loaded `#dashboard-details` charts) -- `refreshDashboardSummary()`
  gained its own `api.listLogs()` call, in parallel with its existing
  fetches, rather than reusing an already-fetched value.
- **Out of scope**: renaming/restructuring the underlying metrics
  themselves -- the note's own "maybe other metrics are best" is left as
  an unscoped future idea, not decided here. This phase is a
  comprehension/labeling fix over already-correct numbers, not an engine
  change.
- **Testing**: a `Dashboard_test.py` case asserting the new subtitles and
  the logged-intake tile render with the expected text/values.

#### Phase 5.7 — Log editing

Problem: `PUT /api/logs/<id>` (`log_routes.py`), `LogManager.update_log`,
and the client's `api.updateLog()` already exist end-to-end -- there's
simply no UI to trigger them, so only Create and Delete are reachable from
the Log view's table today.

- An "Edit" button (`views.js`'s `renderLogTable`, next to the existing
  Delete button, `.edit-log-btn`) opens the same 4-step wizard already
  used for creating a log, pre-filled with that row's full values
  (weight/waist/neck/intake/steps/cardio/macros/granularity). `app.js`
  gains `state.editingLogId` (`null` while creating) and an
  `enterEditMode(log)`/`exitEditMode()` pair.
- **The log's date is not editable in edit mode** -- the wizard's date
  label reads "Editing log for `<original date>`" instead of "Logging for
  `<navigated day>`", sidestepping a real conflict: the wizard's date is
  otherwise bound to the Log view's day/week navigator (Phase 4.4), which
  wouldn't necessarily match the edited row's own date (e.g. editing a
  Monday log while week view also shows a Thursday one). Every other
  field stays editable.
- The wizard's Save button reads "Save changes" and submits via
  `api.updateLog(state.editingLogId, payload)` instead of
  `api.createLog(payload)` while in edit mode; a "Cancel" affordance
  returns to create-mode without saving. After a successful edit, the
  view refreshes and re-enters create-mode for the currently navigated
  day/week (same as after a create).
- **Out of scope**: bulk edit, changing a log's date/granularity via edit,
  any new undo/audit-log UI (the server already audits log changes per
  Phase 1.1 -- this phase surfaces no new audit data, just the edit path
  itself).
- **Testing**: a new `Log_test.py` case -- editing a log's weight through
  the wizard updates the table row in place (same `log_id`, no new row
  created) and the change round-trips through a page reload.

#### Phase 5.8 — Split Account into Profile-only; Goal lives solely in the Plan tab (done)

Problem: the Account view's `#profile-form` still has Target body
fat/Weekly rate fields that, on save, call the *same* `PUT /api/users/me`
used to create a brand-new, unpreviewed goal plan -- a second, blunter
path to change your goal that completely bypasses the Plan tab's existing
preview-then-commit flow (`GET /api/plan/preview` -> commit), which is
confusing and lets a goal change happen with no preview of its
consequences first.

- Account's `#profile-form` (`index.html`) drops the Target body
  fat/Weekly rate fields -- Height/Sex/Birthdate only. `app.js`'s
  profile-form submit handler stops sending `target_bf`/`weekly_rate` in
  its payload.
- The Plan tab remains the **only** place a goal changes, via its
  existing preview -> commit flow -- no server change, since that commit
  path already reuses the exact endpoint Account used to call directly.
- Directly complements Phase 5.2: once both land, `target_bf`/
  `weekly_rate` never appear anywhere except inside the Plan tab's own
  preview/commit flow, for both a brand-new account and an existing one
  editing later.
- The form's heading changes from "Goal &amp; profile" to plain "Profile",
  and `views.js`'s `fillProfileForm` drops the two lines populating the
  now-removed fields.
- **Testing**: a new `client/test/browser/Account_test.py` (no Account-view
  browser test existed before this phase) -- the register and profile
  forms both render with no goal fields, and editing height/sex/birthdate
  round-trips through a page reload without moving the active goal's
  `target_bf`/`weekly_rate` (read back via the Plan tab's own form,
  populated from `GET /api/users/me`); `Client_test.py` gained a markup
  assertion that both forms lack `target_bf_pct`/`weekly_rate_pct` while
  the Plan tab's own form still has them.

#### Phase 5.9 — Goal section: target-first framing with delta-to-goal tiles (done)

Source: further consideration after Phase 4.2 shipped the Goal summary
section, not one of `things-to-improve.txt`'s original eight items. Today's
"Body fat vs target" and "Weight to goal" tiles both lead with the
*current* number and bury the actual target in a plain-text subtitle (body
fat) or omit it entirely (weight, which only ever showed the remaining
distance in kg, per Phase 5.5's fix, with no visible target figure at
all). The ask: flip both tiles to lead with the **target** figure -- the
number the user is actually working toward -- and use an arrowed,
`.delta`-style subtitle (the same visual language the Weight & Body
Composition section above it already uses for week-over-week change) to
show the remaining distance to close.

- **"Body fat vs target" becomes "Target body fat"**: the big value is now
  `profile.target_bf` (was `latest.body_fat`); the subtitle is the signed
  gap in the direction of travel, `(target_bf - body_fat) * 100`
  percentage points, e.g. current 19.8% vs target 15.0% renders "▼ -4.8%
  to goal". Falls back to showing current body fat with no subtitle if a
  profile/target isn't loaded yet (defensive, matches the prior ternary).
- **"Weight to goal" becomes "Target weight (keep lean)"**: the
  big value is now `latest.final_weight_kg` (the goal weight, assuming
  today's lean mass is preserved and only fat mass changes -- literally
  what `Trajectory.compute_final_weight` computes) instead of the bare
  remaining-kg figure; the subtitle is the signed gap,
  `final_weight_kg - (fat_mass_kg + lean_mass_kg)`, e.g. "▼ -9.0 kg to
  goal" for a cut still 9kg out, or "▲ +9.0 kg to goal" for a bulk still
  short of its target. This is the same Phase 5.5 formula, sign-flipped
  into "remaining distance in the direction of travel" instead of an
  absolute value.
- A new shared `formatGoalDelta(remaining, unit)` helper (`views.js`,
  alongside the existing `formatDelta` used for week-over-week change)
  renders the arrow (▲/▼/–, reusing `formatDelta`'s convention) plus the
  signed value with the unit appended directly (no space for `"%"`, a
  leading space for `" kg"`) and a trailing "to goal" -- distinct from
  `formatDelta` only in that suffix and the no-space-before-`%` case
  Phase 5.6's calorie subtitles don't need. Normalizing through
  `Number(remaining.toFixed(1))` before picking the arrow/sign avoids a
  stray "-0.0" once a goal is essentially reached.
- "Weeks to goal" and "Direction" tiles are unchanged.
- **Testing**: `Dashboard_test.py`'s existing summary-render assertions
  are updated for the new labels ("target body fat", "target weight"
  instead of "weight to goal"); the existing Phase 5.5 regression test is
  adapted to read the new delta subtitle (parsed from its rendered text)
  against the same `(final_weight_kg - current_weight)` formula fetched
  independently from `GET /api/metrics/latest`, rather than the tile's
  big value, since the big value itself is now the target weight, not a
  distance.

#### Phase 5.10 — Alert new accounts about their auto-assigned default goal (done)

Source: further consideration after Phase 5.2 shipped goal-free
registration, not one of `things-to-improve.txt`'s original eight items.
Problem: since Phase 5.2, a brand-new account's first goal (15%/22% body
fat by sex, 0% weekly rate) is silently assigned rather than chosen -- a
first-time user has no way to know a placeholder goal exists at all,
let alone that visiting the Plan tab is how they'd set a real one.

- A new detector, `Alerts._unconfigured_goal_alerts(goal,
  goal_history_count)` (`services/composition/Alerts.py`), fires a new
  `"unconfigured_goal"` alert type -- unlike every other detector in this
  module, it needs no logged week at all (no `CompositionResult`
  dependency), so it can flag a fresh account before any log exists.
- **No schema change.** Rather than adding an `is_default` flag to
  `goal_plans` (a migration), the check is purely inferential and
  self-cleaning: it only fires when `goal_history_count == 1` (this is
  the account's one-and-only-ever goal plan, via
  `GoalPlanManager.list_history`) **and** `weekly_rate` is still exactly
  `0.0` (within a `1e-9` epsilon, mirroring
  `Trajectory.compute_weeks_to_goal`'s own zero-rate guard) -- the literal
  "no plan yet" signal, since any deliberately chosen goal necessarily has
  a nonzero rate. Committing any goal via the Plan tab always historizes
  a new `goal_plans` row (`GoalPlanManager.create_goal_plan`), so
  `goal_history_count` becomes `2` and this can never re-trigger, even if
  the user lands on the same numbers again.
- `detect_alerts()` gains an optional `goal_history_count` parameter,
  following the same "omit it, skip that detector" convention every other
  optional signal (`gain_quality`/`reconciliation`/`logs`/`macro_targets`)
  already uses. `AlertSyncService.sync_alerts()` computes it via
  `len(goal_plan_manager.list_history(user_id))` and passes it through.
- **No client change at all.** `GET /api/alerts` already runs on every
  Dashboard visit regardless of whether any logs exist
  (`refreshDashboardSummary()`), and `renderAlerts()` already renders
  whatever comes back generically -- the new alert flows through the
  exact same persisted, dismissible pipeline (`alert_log`'s
  `UNIQUE(user_id, type, date)`, keyed on the goal's `start_date`) every
  other alert already uses, including its existing dismiss button.
- Like every other alert here, this one is a persisted historical record,
  not a live-recomputed state: once dismissed (or left alone), it follows
  the same acknowledge/history lifecycle as any other alert -- it does
  not disappear on its own the moment a real goal is set, only stops
  being freshly re-detected.
- **Testing**: new `Alerts_test.py` cases (fires with zero
  `CompositionResult`s; skipped once `goal_history_count` moves past `1`;
  skipped for a deliberately-chosen nonzero rate; skipped with no goal;
  skipped when `goal_history_count` is omitted); a new `Api_test.py` case
  registering through the omission path (`POST /api/users` with no
  `target_bf`/`weekly_rate`) and confirming `GET /api/alerts` surfaces it
  immediately; a new `Dashboard_test.py` case confirming the alert renders
  on a fresh account's Dashboard and dismisses via the existing
  alert-dismiss button.

## Android app

JustFitting ships as an installable Android app by bundling the static
web client **inside** the APK using [Capacitor](https://capacitorjs.com/),
rather than opening a hosted URL through a browser wrapper. The Flask API
is called remotely over HTTP(S), exactly like the browser client — no
on-device Flask, no native UI rewrite.

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

Node.js and a JDK are conda dependencies (`environment.yml`), right
alongside Python — `scripts/install.sh`/`update.sh` (or `conda env update
-n justfitting -f environment.yml --prune`) install them into the
`justfitting` env for free. No separate Node installer, no admin rights,
no Docker required.

```bash
conda activate justfitting
npm install                 # @capacitor/core, @capacitor/cli, @capacitor/android
npm run android:add         # one-time: scaffolds android/ via `npx cap add android`
```

### Android SDK, without Android Studio

Only the Android **SDK** is required to build; the Android Studio **IDE**
is optional convenience. Everything below is project-scoped or set for a
single command's duration — no global/System or User environment
variable, so it can't conflict with other projects on the same machine:

1. Download the **command line tools** (not the full IDE) from
   [developer.android.com/studio#command-tools](https://developer.android.com/studio#command-tools)
   and unzip anywhere under your user profile, e.g.
   `%LOCALAPPDATA%\Android\Sdk\cmdline-tools\latest\` (the zip's own
   top-level `cmdline-tools` folder needs renaming to `latest`).
2. Point Gradle at the SDK via `android/local.properties` — the same file
   Android Studio itself always writes, already gitignored since the path
   is machine-specific:
   ```properties
   sdk.dir=C:/Users/<you>/AppData/Local/Android/Sdk
   ```
3. Install what the build needs, pointing `sdkmanager` at the SDK
   directly instead of via an environment variable:
   ```bash
   sdkmanager --sdk_root="%LOCALAPPDATA%\Android\Sdk" --licenses
   sdkmanager --sdk_root="%LOCALAPPDATA%\Android\Sdk" "platform-tools" "platforms;android-34" "build-tools;34.0.0"
   ```
4. Gradle needs a JDK 17+ on `JAVA_HOME`; set it for the current shell
   only (the conda env already has one) rather than globally:
   ```powershell
   $env:JAVA_HOME = "$env:LOCALAPPDATA\anaconda3\envs\justfitting\Library"
   ```

### Building the client for a target

The API base URL is injected the same way as the web build
(`scripts/build_static_site.py`, `window.JUSTFITTING_API_BASE_URL` in
`api.js`) — just a different target URL per case:

| Target | Command |
| --- | --- |
| Production | `python scripts/build_static_site.py https://YOUR_PRODUCTION_API_URL` |
| Android emulator | `python scripts/build_static_site.py http://10.0.2.2:5000` (the emulator's alias for the host's `localhost`) — also `npm run build:web:android` |
| Real device on the same LAN | `python scripts/build_static_site.py http://LOCAL_MACHINE_LAN_IP:5000` |

```bash
npm run android:sync        # build:web:android + `npx cap sync android`
```

### Building and running the app

Three ways to get it onto a device, in increasing order of convenience:

- **`npm run android:open`** — opens the project in Android Studio, if
  installed; build/run from there.
- **`android\gradlew.bat -p android installDebug`** — builds and installs
  directly onto a connected device (enable USB debugging, confirm with
  `adb devices`) or a running emulator. No Android Studio needed.
- **`npm run android:apk`** — builds a debug APK and copies it to the repo
  root as `JustFitting-debug.apk` (gitignored) — one file to send over
  email, a cloud drive, or a messaging app and sideload, with no live
  device connection needed at build time. On the phone, enable **"Install
  unknown apps"** for whichever app received it, then open the file. This
  is a debug-signed APK — fine for sideloading onto your own device, not
  for Play Store distribution.

The Android emulator needs hardware-accelerated virtualization
(HAXM/Windows Hypervisor Platform), which needs admin rights on Windows —
the two device-based options above don't.

After editing client code, re-run `npm run android:sync` to refresh the
bundled `dist/` before rebuilding. For a production release, point
`build_static_site.py` at the production URL, run `npx cap sync android`,
then build a signed AAB/APK (`gradlew.bat bundleRelease` or Android
Studio's Build menu, with a real keystore — not covered here).

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
- **CORS**: the server reads `JUSTFITTING_CORS_ORIGINS` from the
  environment (`server/src/api/app.py`) instead of hardcoding origins.
  Capacitor's Android WebView serves the bundled UI from the
  `https://localhost` origin by default, so if you lock
  `JUSTFITTING_CORS_ORIGINS` down to an allowlist (rather than the
  default `*`), include `https://localhost` in it.

### Status

`android/` is scaffolded and committed (Capacitor's convention, since the
native project holds Gradle/signing/manifest customizations `cap sync`
doesn't regenerate). The full toolchain above — conda-managed Node/JDK,
the command-line SDK tools, and `npm run android:apk` — has been verified
to produce a working debug APK, with no admin rights and no global
environment variables anywhere in the chain. Not done: a release keystore/
signed build, and an emulator system image (needs admin — use a real
device instead, see above).

### Future: local/offline data mode (design note, not implemented)

Today the Android app is purely a remote-API client, same as the web app.
A natural next step once this need arises is a data-access layer inside
the client JS that can choose between **remote API mode** (today's
behavior, unchanged), **local storage mode** (logs/metrics cached or
entered offline, most likely via a Capacitor storage/SQLite plugin), and
a future **sync mode** reconciling the two. This is only a design
direction, not scoped work — running the full Flask server on-device is
explicitly out of scope unless a strong reason emerges later.

## The Team

Danel Arias — University of Deusto, Bilbao.
