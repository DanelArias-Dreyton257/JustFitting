# JustFitting
[![CI](https://github.com/DanelArias-Dreyton257/JustFitting/actions/workflows/ci.yml/badge.svg)](https://github.com/DanelArias-Dreyton257/JustFitting/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/DanelArias-Dreyton257/JustFitting)](https://github.com/DanelArias-Dreyton257/JustFitting/releases/latest)

A weekly body-composition tracker. Log a handful of easy home measurements
— weight, waist, neck, mean calorie intake, mean daily steps — and
JustFitting derives your body-fat %, fat/lean mass split, a full energy
model (BMR / NEAT / TDEE / target calories), a goal trajectory (target
weight, weekly deficit, weeks-to-goal), and a forecast of future weeks.

Try it out! https://danelarias-dreyton257.github.io/JustFitting/ — log in
with `admin_cut` / `adminadmin` (a cut, resembling Demo_cut) or `admin_bulk` /
`adminadmin` (a bulk, resembling Demo_bulk) to see a populated dashboard. The
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
| `seed_demo_data.sh` | Register `admin_cut`/`admin_bulk` (both `adminadmin`) and seed their Demo_cut (cut) and Demo_bulk (bulk) reference series. No-op per-account if already seeded. |
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

Demo_cut worked example (`H=176, sex=1, birthdate=2001-08-22`) -- registered
targeting 17% body fat at -0.5%/week, then switched on 2026-05-01 to a
steeper 15% target at -1%/week (the demo seed's Phase 5.3 two-goal
history, below). Last real record 2026-06-26 (`W=90.7, waist=80.0,
neck=35.0, steps=5000`), computed under the active (second) goal
(`target_bf=0.15, weekly_rate=-0.01`):

```
BMI 29.28 | BF 19.91% | FatMass 18.06 kg | LeanMass 72.64 kg
BMR 2098.08 | TDEE 2583.14 | TargetCal 1470.92
Wobj 90.09 | DailyDeficit 1001.0 | Wfinal 85.459 | Weeks 5.98
```

BMI/BF/FatMass/LeanMass/BMR/TDEE/Wfinal only ever depend on the logged
anthropometric data and `target_bf` (unchanged at 0.15 across both
goals here), never `weekly_rate` -- only Wobj/DailyDeficit/TargetCal/Weeks
shift with the goal change, since those are the only formulas above that
read `r`.

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
  numbers exactly, never Demo_bulk's own calibration. `GET`/`PUT
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

Source: `things-to-improve.txt`, Demo_cut's own notes from the first round of
beta-testing the shipped v1.0.0 app. Five items, roughly in the order
they unlock each other (2-5 lean on 1, and on each other); this phase's
sub-phases track them 1:1. **All five, Phase 4.1-4.5, are done.**

#### Phase 4.1 — Consolidated top navigation (hamburger menu) (done)

Problem: the top bar packed eight destinations (Dashboard, Log,
Projection, Plan, Alerts, Report, Settings, Account) plus Logout into one
non-wrapping flex row, which crowded/overflowed on narrow viewports --
the primary width for the Android app -- and was already visually busy
on desktop. No responsive/mobile nav pattern existed before this phase.

- The always-visible nav row is replaced by a single hamburger icon
  button (`#nav-toggle`) that toggles a `.nav-menu` panel listing the
  same eight destinations plus Logout, at every viewport width (not just
  behind a mobile breakpoint).
- Full keyboard/accessibility support: `aria-expanded`/`aria-controls`,
  `role="menu"`/`"menuitem"`, close-on-outside-click, Enter/Space/Escape,
  focus returns to the toggle on close.
- Purely client-side: no server/API/DB changes, no `ENGINE_VERSION`
  implications.

#### Phase 4.2 — Simplified dashboard-as-home summary (done)

`things-to-improve.txt` item 2: land on a simpler dashboard summary
first -- a last-logged weight/body-fat/lean-mass-and-change section, a
calories section, and a goal section (achieved vs. target, projected
weeks-to-complete) -- rather than today's full chart grid as the
landing view. A client-only change: every figure the new summary needs
was already computed and exposed by existing endpoints, so no engine
work, migration, or `ENGINE_VERSION` bump was needed.

- `#view-dashboard` splits into an always-visible summary -- three
  `.stat-row` card sections (Weight & Body Composition, Calories, Goal)
  -- and a collapsed "Full charts & advanced stats" section holding the
  existing 12-chart grid, lazy-loaded only on first expand rather than
  fetched on every dashboard load.
- The collapsed section's tile row now only surfaces the genuinely
  *advanced* figures (TEF, cumulative fat ratio, energy-balance error,
  average weekly increment, deviation from goal rate), since
  Weight/Body fat/Lean mass/To-target/Weeks-to-goal/Adherence are all
  covered by the new summary sections.
- Manually verified against both seeded demo accounts: `admin_cut`'s
  summary reproduces the README's own Demo_cut worked example; `admin_bulk`
  renders the same layout with upward weight/lean-mass deltas and a
  "Bulk" direction badge.
- No server/API/DB changes.

#### Phase 4.3 — Projected-weeks toggle on Dashboard charts (done)

`things-to-improve.txt` item 3: a toggle on the Dashboard's charts to
overlay the forecast alongside real data, with a dashed vertical line
marking the last logged day, so the user sees "the next N weeks"
directly on the chart they're already looking at instead of switching to
the separate Projection view.

- Applies to the five line/multi-line charts with a real "future" to
  extrapolate — Weight, Body fat %, Target calories, Waist/Neck, and Goal
  trajectory — not Steps or the two bar charts.
- `GET /api/projection` gained `estimated_weight`/`estimated_waist`/
  `estimated_neck` fields (purely additive, no `ENGINE_VERSION` bump) so
  the Dashboard can chart forecasted perimeters, not just weight/BF/
  calories.
- A checkbox ("Show next N weeks") plus a weeks selector (4/8/12, default
  4) toggles the overlay; forecast points render as hollow markers with a
  "(forecast)" tooltip to distinguish them from real data, and a "Last
  logged" dashed marker line stays fixed regardless of how many weeks are
  shown.
- Turning the toggle off redraws every chart from the unmodified base
  series — the forecast is never persisted, matching the read-only
  nature of `GET /api/projection`.

#### Phase 4.4 — Redesigned log capture (day/week view) (done)

`things-to-improve.txt` item 4: replace the Log view's current layout --
the wizard on top, then one unbounded table of every log the account has
ever created underneath -- with a calendar-style navigator (prev/next
arrows, a day/week toggle, a date picker) that puts the wizard "inside"
a chosen day, defaults to today, and shows only that day's (or that
week's) logs below it. Client-only, like Phase 4.2/4.3 -- `GET /api/logs`
already returns every log for the account, so day/week view is a
client-side filter over already-fetched data. No migration,
no `ENGINE_VERSION` bump, no server route changes.

- The wizard's Date field becomes a read-only label bound to the
  navigator's selected day, instead of a freely-editable date input --
  you pick the day via the navigator first, then the wizard logs *for*
  that day.
- "Week" means the ISO calendar week (Monday-Sunday), the same grouping
  `LogResampler.resample_to_weekly` uses server-side for daily-tagged
  rows.
- No inline edit UI, pagination, or new date-range API were added in this
  phase (edit UI followed in Phase 5.7). The old "every log ever" table
  is retired, not relocated -- full history stays reachable via the
  date-picker, the Report view's full weekly series table, and JSON
  export.

#### Phase 4.5 — Retire the standalone Projection view (done) — Phase 4 complete

`things-to-improve.txt` item 5: now that 4.3 (Dashboard forecast toggle)
and 4.4 (Log view day/week navigator) have both shipped, the dedicated
Projection view/tab is removed entirely -- forecast data becomes a
Dashboard toggle (already true since 4.3) and appears directly in the Log
view as a tagged row instead. Client-only: `GET /api/projection` already
returns everything needed, so this is removing UI and reusing an
existing fetch, not new server work.

- The standalone view, its nav entry, and `refreshProjection()`/
  `renderProjectionTable()` are removed.
- A projected row now appears directly in the Log table, gated by a
  Settings-view preference (`localStorage`-persisted, default on) rather
  than a per-view toggle, since it's a display preference rather than an
  engine input. It fires when the navigator's selected day/week has no
  logged row yet and falls after the last real logged date.
- The synthetic row uses the same columns as a real log, styled
  italic/muted with a "projected" badge and no Delete button. Fields the
  forecast never observed (intake, steps, cardio, macros) render as
  "--" rather than fabricated.
- How far to forecast is derived from navigation (days between the last
  real log and the selected day/week-end, clamped 1-52), not a separate
  input -- removing the standalone view means its
  base/activity/trend-model configurability is gone entirely, an
  accepted trade-off for the simplification the note asks for.

**With this phase, Phase 4 (UX refinement: beta-testing feedback) is
complete** -- all five `things-to-improve.txt` items from the first round
of beta-testing are shipped.

### Phase 5 — Beta-testing feedback, round 2 (done)

Source: `things-to-improve.txt`'s "Things to change (Beta-testing) Phase 5"
section, Demo_cut's second round of beta-testing notes -- eight items,
mostly independent of each other (unlike Phase 4's chained items), plus
two further-consideration items (5.9, 5.10) beyond the original eight.
**All ten sub-phases, Phase 5.1-5.10, are done.**

#### Phase 5.1 — Self-versioning service-worker cache (done)

Problem: every prior phase's Housekeeping note ended with a
manually-bumped `sw.js` `CACHE_NAME` -- easy to forget, and pure busywork
a machine can do itself.

- `sw.js` computes its own cache name at runtime: it fetches every
  `APP_SHELL` file fresh, hashes their concatenated bytes
  (`crypto.subtle.digest("SHA-256", ...)`), and uses the hash, prefixed
  `justfitting-shell-`, as the cache name. `activate` deletes every other
  `justfitting-shell-*` cache.
- Any future edit to a shell file changes the hash automatically, so the
  old cache is purged on the next `activate` -- no manual version bumps
  needed going forward.
- Verified manually (DevTools Application tab, and a Playwright-driven
  check) that the cache name is a computed hash and the service worker
  activates normally.

#### Phase 5.2 — Registration no longer asks for a goal; sane per-sex defaults (done)

Problem: `POST /api/users` required `target_bf`/`weekly_rate` and created
a goal plan immediately at registration. The note wants account creation
decoupled from goal-setting: a new account should start from a harmless
default, with the user visiting the Plan tab only once they actually want
to set a real goal.

- New defaults (`services/composition/constants.py`): 15% body fat
  (male) / 22% (female), 0% weekly rate. `UserManager.register()`'s
  `target_bf`/`weekly_rate` become optional, resolved from these
  constants by `sex` when omitted -- a goal plan is still always created,
  just invisibly defaulted rather than user-chosen at signup.
- The register form drops the goal fields entirely; registration becomes
  just username/email/password/height/sex/birthdate.
- Ties into Phase 5.8 below (goal editing lives only in the Plan tab from
  here on, for both new and existing accounts).
- Bug found and fixed along the way: `Trajectory.compute_weeks_to_goal`
  divided by `ln(1 - weekly_rate)`, which is exactly `0` at
  `weekly_rate = 0` -- a latent `ZeroDivisionError` the new default path
  would trigger immediately. Guarded the same way
  `IncrementAnalytics.py` already guards its own zero-rate case.

#### Phase 5.3 — Scope computed series/charts/projections to the active goal's period (done)

Problem: computed series (metrics, charts, alerts, projections) were
always fit over every real log the account ever made, applying only the
currently active goal's `target_bf`/`weekly_rate` uniformly across all of
it -- so changing goals (e.g. finishing a cut, starting a bulk) silently
recomputed history under the new goal and fed pre-change data into the
forecast's trend regression.

- A new `GoalPlanManager.active_period_start(user_id)` returns the active
  goal's `start_date` only once the account has actually changed its goal
  (more than one historized goal); otherwise `None`, meaning "use
  everything" -- keeping a single-goal account a complete no-op.
- `MetricsSeriesService.compute_series_for_user` and the projection
  routes filter logs to that period before resampling/computing. `GET
  /api/logs` (raw history, the Log view's table, `/export`) is
  unaffected -- only derived series are scoped.
- The engine threads an `initial_prev_weight_kg` context value through
  `compute_series` so the first row of a new goal period still has a real
  predecessor, avoiding a false "reset to zero deviation" spike on the
  goal-trajectory chart at every goal change.
- Both demo accounts (`admin_cut`, `admin_bulk`) now seed a two-goal
  history so this scoping is exercised out of the box; the "Demo_cut
  worked example" above reflects `admin_cut`'s actual active goal.

#### Phase 5.4 — Log wizard defaults to the last log's perimeters (done)

Problem: the wizard always opened with blank Waist/Neck fields, even
though most weeks a person's perimeters barely change.

- The wizard now pre-fills `waist_cm`/`neck_cm` from the most recent real
  log across the whole account, at every "fresh wizard" reset point
  (entering the Log view, switching day/week, after a save); a brand-new
  account with no real logs still opens blank.
- Scoped to perimeters only -- weight stays blank (it's meant to be
  re-measured every time) and intake/steps/cardio/macros stay blank too
  (today's actual entry, not a carry-forward).

#### Phase 5.5 — Fix "Weight to goal" (was showing the weekly delta, not the total remaining) (done)

Problem (confirmed bug, reported as "always showing 0.5kg"): the Goal
summary's "Weight to goal" tile read `weight_to_shed_kg`, this week's
incremental target change, not the total remaining distance to the goal
-- for a steady weekly rate on a large body it always lands around the
same figure regardless of how close the goal actually is.

- Client-only fix: "Weight to goal" now computes from `final_weight_kg`
  (the goal weight already returned by `MetricsDTO`) minus current total
  weight -- the real remaining distance. `weight_to_shed_kg` itself is
  untouched, since it's still correct for its actual job driving
  `daily_deficit`/`target_calories` inside the engine.

#### Phase 5.6 — Clearer Calories summary: label what each figure means (done)

Problem: Target calories, TDEE, and Adherence were presented as three bare
numbers with no explanation of what they are or how they relate --
TDEE is estimated expenditure (never intake), and Adherence is a mean
deviation across real-intake weeks, not simple arithmetic between the
other two tiles.

- Each tile gains a short subtitle clarifying its meaning ("what to eat",
  "estimated calories burned", "actual vs target/day").
- A fourth tile, this week's logged intake, is added so the three
  genuinely comparable numbers (ate / should-eat / burn) sit together,
  with Adherence (a derived comparison) last.
- Out of scope: renaming/restructuring the underlying metrics themselves
  -- this is a labeling fix over already-correct numbers.

#### Phase 5.7 — Log editing (done)

Problem: `PUT /api/logs/<id>`, `LogManager.update_log`, and
`api.updateLog()` already existed end-to-end -- there was simply no UI to
trigger them, so only Create and Delete were reachable from the Log
view's table.

- An "Edit" button opens the same 4-step wizard used for creating a log,
  pre-filled with that row's values. The log's date and granularity
  aren't editable in edit mode (the wizard's date is otherwise bound to
  the navigator, which wouldn't necessarily match the edited row's own
  date); every other field stays editable.
- Saving submits via `api.updateLog()` instead of `api.createLog()`; a
  Cancel affordance returns to create-mode without saving.

#### Phase 5.8 — Split Account into Profile-only; Goal lives solely in the Plan tab (done)

Problem: the Account view's profile form still had Target body
fat/Weekly rate fields that saved through the same endpoint used to
create a brand-new, unpreviewed goal plan -- a second path to change your
goal that bypassed the Plan tab's preview-then-commit flow entirely.

- Account's profile form drops the goal fields -- Height/Sex/Birthdate
  only. The Plan tab remains the only place a goal changes, via its
  existing preview -> commit flow.
- Complements Phase 5.2: together, `target_bf`/`weekly_rate` never appear
  anywhere except inside the Plan tab's preview/commit flow, for both a
  new account and an existing one editing later.

#### Phase 5.9 — Goal section: target-first framing with delta-to-goal tiles (done)

Source: further consideration after Phase 4.2, not one of
`things-to-improve.txt`'s original eight items. The Goal summary's tiles
led with the current number and buried (or omitted) the actual target.

- "Body fat vs target" becomes "Target body fat": the big value is now
  the target itself, with the signed gap to it as a subtitle (e.g. "▼
  -4.8% to goal").
- "Weight to goal" becomes "Target weight (keep lean)": the big value is
  now the goal weight (`final_weight_kg`), with the signed remaining
  distance as a subtitle -- the same Phase 5.5 formula, sign-flipped into
  "remaining distance in the direction of travel."

#### Phase 5.10 — Alert new accounts about their auto-assigned default goal (done)

Source: further consideration after Phase 5.2, not one of
`things-to-improve.txt`'s original eight items. Since Phase 5.2, a
brand-new account's first goal is silently assigned rather than chosen --
a first-time user has no way to know a placeholder goal exists, let alone
that the Plan tab is how they'd set a real one.

- A new `unconfigured_goal` alert detector fires when an account has only
  ever had one goal plan and its weekly rate is still exactly `0%` -- the
  literal "no plan yet" signal, since any deliberately chosen goal
  necessarily has a nonzero rate. No schema change: purely inferential,
  and self-cleaning once a real goal is committed (which always adds a
  new historized goal-plan row).
- Flows through the existing persisted, dismissible alerts pipeline with
  no client change needed.

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

Demo_cut Arias — University of Deusto, Bilbao.
