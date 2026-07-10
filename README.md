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
**Android app** below. Phase 6 (done) adds a genuine on-device runtime
dependency for the Android target specifically — an embedded Python
interpreter running the server itself — without changing anything above
for the web deployment; see **Android app → Embedded on-device server**.

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
`E_i`, steps `s_i` — every formula below is unchanged by Phase 9.1's data-
model split; `c_i`/`n_i` are resolved from the sporadically-logged
`body_measurements` history (held "static" from one reading to the next)
rather than read off the same row as `W_i`/`E_i`/`s_i`, but arrive at
`compute_row` as the exact same values either way.

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
- **Dashboard steps chart doesn't expand a daily-logged week.**
  Since Phase 1.2, `app.js`'s `refreshDashboard` merges `GET /api/logs`
  (raw, one row per day for a daily-granularity account) with `GET
  /api/metrics/series` (one row per *week*, by `log_id`, per Phase 3.3's
  resampling) client-side. A daily-logging week's steps chart point only
  lands on the resampled week's representative day; the other logged days
  in that week don't get their own point. This is a known, documented
  consequence of the engine staying weekly-cadence, not a bug -- fixing it
  would mean reworking that merge to resolve by ISO week instead of
  `log_id`, or building a real per-day chart on top of Phase 3.3's
  now-available `LogResampler.daily_view`. Not scoped into a phase since
  the raw log table already shows every logged day correctly. (Phase 9.2
  incidentally resolved this exact limitation for perimeters specifically
  -- the Waist/neck chart no longer merges with `body_logs` at all, since
  it reads `GET /api/body-measurements` directly.)
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

### Phase 6 — Embedded on-device server for Android (done, v2.0)

Today's Android app (Phase 2) is a remote-API client: the WebView UI runs
on-device, but every request still goes out over HTTP(S) to the Render
deployment, exactly like the browser client. Phase 6 changes that for the
Android target only — the same Flask API and SQLite persistence the
server already is runs *inside* the APK's own process, reachable only at
`http://127.0.0.1`, the same relationship `scripts/run.sh`'s two local
terminals already have today, just packaged into one app instead of two
dev processes. The web deployment (GitHub Pages + Render) is completely
unaffected — it keeps talking to a remote API exactly as it does now,
just a different build target of the same `dist/` client. See **Android
app → Embedded on-device server** below for the full design — verified
end-to-end on a real device: registration, logging, a real computed
Dashboard, data surviving a force-close/reopen, and full functionality in
Airplane Mode (proving it never touches Render).

(`things-to-improve.txt` separately lists its own unscheduled "Phase 6" —
four smaller UX items from a further beta-testing round, unrelated to
this. Resolved below: this on-device-server work keeps the number 6;
`things-to-improve.txt`'s leftover items are renumbered **Phase 8**.)

### Phase 7 — Data portability & phone health-app sync (done, v3.0)

Two independent capabilities bundled into one release: richer manual
data import (CSV alongside the existing JSON round-trip), and, Android
app only, pulling step counts and calorie/macro logging on demand (a
manual "Sync now" button, see 7.3/7.5 — not an automatic background
pull, at least for this first version) from the phone's own health apps
via Android's Health Connect. This claims the "Phase 7" number left open
above; `things-to-improve.txt`'s
own leftover four items (a goal progress bar, a "last logged" info line,
a missing-log alert, and a >1%/week cut-rate alert) are now scheduled as
**Phase 11** (v5.1) — see the roadmap continuation below, after Phase
7.7, for the full plan covering these and every other remaining
`things-to-improve.txt` item.

#### Phase 7.1 — Harden the existing JSON import (done)

`POST /api/users/me/import` already existed and round-tripped
`GET /api/users/me/export`'s shape — this phase fixed four real gaps:
**silent field loss** (`granularity`/macro fields were dropped on
re-import — every `BodyLogDTO` field now passes through, same as
`POST /api/logs`), an **unhandled duplicate-date crash** (`body_logs`'
`UNIQUE(user_id, date)` raised an uncaught `sqlite3.IntegrityError`;
`LogManager.get_by_date` now checks first and records a
`"duplicate date"` skip instead), a **forged `source` field** (an
imported row could claim `source="projected"`, indistinguishable from a
real forecast row — imports now always force `source="real"`), and **no
feedback** on what was skipped (the response now carries
`skipped: [{row, reason}]`; `views.js`'s `renderImportSummary` shows an
"Imported N, skipped M (reasons)" line instead of a silent refresh). No
schema change. Covered by four new `Api_test.py` cases plus the existing
round-trip test. See `docs/import_format.md` for the full field
reference used by both this route and the CSV path below.

#### Phase 7.2 — CSV import (done)

A second on-ramp into the same hardened pipeline from 7.1, not a
parallel one — the same file input accepts either format. Parsing
happens **client-side** (`client/src/webapp/static/js/csvImport.js`,
`parseCsvLogs(text)`, a small hand-rolled RFC-4180-ish parser — no new
dependency, matching `charts.js`'s hand-rolled-SVG precedent of never
taking on a JS library), turning a `.csv` file into the exact
`{logs: [...]}` shape the JSON path already sends, so 7.1's validation,
dedup, and per-row reporting serve both formats with no duplicated
server logic. Every field is type-coerced client-side (real numbers,
real booleans — Python's `bool("false")` is `True`, so leaving
`intake_is_real` as a raw string would have silently marked every row
real). A downloadable template
(`client/src/webapp/static/justfitting-import-template.csv`) is linked
next to the Import control. Covered by 9 Playwright cases
(`CsvImport_test.py`): type coercion, blank-column omission, the
`bool("false")` trap, quoted fields, and a missing-required-column
error.

#### Phase 7.3 — Android Health Connect bridge (done, verified on a real device)

Formally schedules the "Automatic steps import" idea Phase 2.1 listed as
unscheduled since Phase 2, adding calorie/macro import alongside it —
confirmed feasible via both target apps' own settings, not a proprietary
integration: **Samsung Health** has synced with
[Health Connect](https://developer.android.com/health-and-fitness/health-connect)
since app version 6.22.5, and **Mi Fitness** has its own Health Connect
toggle for Steps — both entirely opt-in on the user's phone, so
JustFitting only ever talks to Health Connect (`androidx.health.connect:
connect-client`, pinned to `1.1.0-alpha08` — the newest release still
compatible with this project's compileSdk 34/AGP 8.2.1; the current
stable `1.1.0` needs compileSdk 36+), never to Samsung's/Xiaomi's own
SDKs directly.

- **minSdk bumps to 26** (Android 8.0, a second bump after Phase 6's
  22→24), which connect-client requires at any version.
- **One deliberate exception to "plain Java, no new bridge language"**:
  connect-client's API is Kotlin-suspend-function-based with no supported
  Java interop path, so `HealthConnectBridge.kt` — the *only* Kotlin file
  in this app — wraps it in `runBlocking` to expose plain synchronous
  methods; everything else, including the new `HealthSyncPlugin.java`
  Capacitor plugin (`isAvailable`/`hasPermissions`/`requestPermissions`/
  `readRecentReadings`) and `MainActivity.java`, stays plain Java.
- `HealthConnectBridge.readDailyReadings` uses Health Connect's own
  per-day aggregation (`aggregateGroupByPeriod`, `StepsRecord.COUNT_TOTAL`/
  `NutritionRecord.*_TOTAL`) rather than summing raw records by hand, with
  `dataOriginFilter` doing per-app filtering.
- **Permission model**: Health Connect scopes permissions by *data type*
  (Steps, Nutrition), not by which app wrote them, so `HealthConnectBridge`
  filters by known package name (Samsung Health:
  `com.sec.android.app.shealth`; Mi Fitness: a small region/firmware alias
  list) to match the ask ("steps from Mi Fitness," not "whichever app").
  Three read-only permissions are requested (`READ_STEPS`/`READ_NUTRITION`,
  plus `READ_HEALTH_DATA_HISTORY` for >30-day reads — see 7.6), but only
  the first two actually gate sync (`requiredPermissions()`), so declining
  history access degrades to a 30-day clamp rather than blocking sync.
- **"Not today" rule**: the sync window's upper bound is always computed
  natively as `LocalDate.now()`, never trusted from the JS caller, and
  Health Connect's own aggregation excludes it — today's count is still
  accumulating and would look like a shortfall read mid-day.
- **Manual sync only, for now**: triggered solely by a "Sync now" button
  (7.5) — no background pull/`WorkManager` job in this first version,
  matching Phase 6's "no execution after the app is swiped away" posture.
  This plugin's own job stops at handing `{readings: [...]}` back to the
  client; what happens next is Phase 7.5's job.

Verified via a real `gradlew assembleDebug` (Kotlin/Java compilation
against the real resolved dependency, manifest merging, packaging) and,
per Phase 7.5's real-device pass below, on an actual phone.

#### Phase 7.4 — Partial logs & independent-source merging (done)

Prompted directly by the sync workflow: Steps (Mi Fitness) and Nutrition
(Samsung Health) are two independent sources that can each succeed, fail,
or not be connected on any given sync, and neither ever provides body
measurements — those stay manual/imported. Goal: however a day's data
arrives (sync first then measurements, measurements first then sync, or
only one automatic source ever working), it converges on one complete
log for that date, not several conflicting ones. Pure data-model
foundation, no UI of its own — Phase 7.5 is what uses it. (An earlier
version of this phase rejected merging across *different* dates within
an ISO week as unneeded complexity; Phase 7.6 found a real case that
needed it after all.)

- **Schema**: `body_logs`'s `weight_kg`, `waist_cm`, `neck_cm`,
  `intake_kcal`, `steps` become individually nullable — `NULL` means "not
  logged yet by any source," not zero (`cardio_kcal`/`intake_is_real`
  stay `NOT NULL`). A direct `SCHEMA` edit, per this project's
  no-migration-runner convention.
  `BodyLog`/`BodyLogDTO`/`LogInput` mark all five `Optional[float]`.
- `validate_log_input` changes from "must be present and positive" to "if
  present, must be positive" for those five (`None` now valid, the same
  treatment the macro trio has had since Phase 3.4); `compute_row` gains
  a completeness guard (`require_complete_log_input`, a clear error
  naming missing fields) as defense-in-depth, not a new reachable path —
  `ENGINE_VERSION` does **not** bump, since a complete row still computes
  byte-for-byte identically.
- **`LogResampler.resample_to_weekly`** generalizes its daily-group
  median/mean aggregation to skip `None`s instead of crashing — a field
  is `None` in the resampled row only if *no* day in that week logged it.
  **`MetricsSeriesService.compute_series_for_user`** excludes a week
  still missing any of the five fields from the computed series (same
  outcome as "never logged," just reachable by "logged but incomplete"
  too) — the raw week still shows in `GET /api/logs`/export.
- **Order- and source-independent merging**: a new
  `LogManager.upsert_fields(user_id, date, fields)` merges given fields
  into an existing row or creates a new partial one, with `granularity`
  set only on first creation — exposed as `PUT /api/logs/by-date/<date>`,
  what Phase 7.5's sync calls once per source, independently, so one
  source failing never blocks the other. `POST /api/logs` and the import
  route (7.1) both relax to accepting any subset of the five fields too.

Covered by new tests at every layer touched — `CompositionEngine_test.py`,
`LogResampler_test.py`, `MetricsSeriesService_test.py`,
`LogManager_test.py`, `Api_test.py`.

#### Phase 7.5 — Sync writes partial logs directly + unified data section (done, verified on a real device)

Supersedes 7.3's original "client-side cache, prefill-only" plan, now
that Phase 7.4 makes a real persisted partial row possible:

- Pressing "Sync now" calls `PUT /api/logs/by-date/<date>` once per
  successfully-read day, per source — Mi Fitness's steps and Samsung
  Health's nutrition/macros merge independently, creating a
  `granularity="daily"` partial row if nothing exists there yet, never
  touching weight/waist/neck (no synced source provides those). Macros
  are only ever sent as a complete trio, matching `validate_log_input`'s
  all-or-nothing rule. A reading is a real row the moment it's synced —
  the original `localStorage`-cache/prefill idea was dropped entirely.
  The sync window is a fixed rolling window (default 7 days, capped at
  90) on every press; re-syncing an overlapping day is harmless (upsert,
  not create).
- **Completing a day** is exactly Phase 5.7's existing edit flow — a
  synced day is already a normal partial row, so open it in the Log view
  and add weight/waist/neck. `renderLogTable`/the wizard now render
  missing fields as a dash/blank instead of the literal string `"null"`,
  and lose their `required` HTML attributes so a genuinely partial save
  isn't blocked client-side (the server is the source of truth, Phase
  7.4).
- **One unified data section**: the Account view's Export/Import controls
  are retitled "Data import, export & sync" and gain, Android only, a
  Connect button (`healthSync.requestPermissions()`, one combined Health
  Connect dialog letting the user grant/deny each data type individually),
  a "Sync last N days" field, a Sync now button, a per-source
  connected/not-connected status line, and a last-synced timestamp
  (`localStorage`). The web build (and any unsupported Android device)
  just shows Export/Import as today.

**Verified end-to-end on a real Xiaomi phone**: register/login against
the embedded on-device server (Phase 6), Connect grants both
permissions, Sync now creates real partial rows via
`PUT /api/logs/by-date`, round-tripping correctly through
`GET /api/logs`. Two real bugs surfaced and were fixed, neither catchable
by static analysis or `gradlew assembleDebug` alone: `aggregateGroupByPeriod`
needs a `TimeRangeFilter` built from `LocalDateTime`, not `Instant` (a
runtime-only constraint); and the Account-view health-sync section was
wired to render on `navigate()`'s `"settings"` case instead of
`"account"`, so it never appeared on a first-ever Account visit. Xiaomi
and Samsung package names were confirmed correct via `dumpsys package`
on-device. One non-bug finding worth recording: a device's source app
(Mi Fitness/Samsung Health) only starts writing into Health Connect from
the moment *it itself* is granted permission to — not retroactively — so
a recently-connected source can genuinely have less history to hand over
than the sync window requests, independent of anything this app does.

**Known limitations not yet exercised**: whether Samsung Health always
writes full per-entry macros (vs. calories-only some days) into
`NutritionRecord` wasn't specifically confirmed; the "Health Connect not
installed" branch (vs. "permission denied") was never hit, since the test
device already had it installed; and permission revocation
(revoke-then-sync) wasn't walked through.

#### Phase 7.6 — Three real-usage Health Connect sync bugs (done)

Three bugs reported after real-world use of Phase 7.3-7.5's sync,
`things-to-improve.txt`'s "FOUND BUGS" section:

- **A >30-day "Sync last N days" value only ever returned 30 days.** A
  hard platform ceiling: without `READ_HEALTH_DATA_HISTORY`, Health
  Connect silently clamps every read to 30 days regardless of the
  requested range. Added as a third permission
  (`HealthConnectBridge.HISTORY_PERMISSION`), but kept out of the actual
  sync gate (`requiredPermissions()` still only needs Steps + Nutrition),
  so declining it just keeps the 30-day clamp instead of blocking sync.
- **A weekly log and same-week daily syncs never actually combined** —
  the more serious of the three, and the one that falsifies Phase 7.4's
  "reject cross-day merging" call. A daily-synced partial week (e.g.
  Mon-Wed, with today's data never included per the "not today" rule)
  plus a separately-entered weekly body-composition log for that same
  week left both rows individually incomplete, surfacing as "cannot
  compute a row missing required fields" when previewing a new goal.
  `LogResampler.resample_to_weekly` now completes a single weekly-tagged
  row sharing its ISO week with a daily group in place — filling only the
  weekly row's still-`None` fields from the daily group's aggregate,
  never overwriting what it already has; two-or-more weekly rows in the
  same ISO week stay untouched, as before. Separately,
  `GET /api/plan/preview` and `GET`/`POST /api/projection` turned out to
  build their engine input from the raw, unresampled log list — unlike
  `MetricsSeriesService`, which already resamples and filters to
  computable rows — so both routes now share that same
  resample-then-filter pipeline, returning a plain 404 instead of a raw
  compute error when nothing computable exists yet.
- **Macros synced from Health Connect stored with excessive decimal
  precision** (`carbs_g: 210.00000000000003`, a sum-of-floats artifact).
  `healthSync.js` now rounds every numeric field to 1 decimal place where
  a native reading enters the JS layer, before it's ever stored.

New coverage: `LogResampler_test.py` (the same-ISO-week merge),
`Api_test.py` (an end-to-end regression on the exact reported scenario),
and a new `HealthSync_test.py` (the rounding behavior). The 30-day-cap
fix specifically still needs a real-device Health Connect sync to
confirm, since no emulator/unit test can exercise Health Connect's own
clamping behavior.

#### Phase 7.7 — Detect history-read feature availability (unscheduled)

Found via real usage after Phase 7.6 shipped: on one device the "Additional
access" history toggle never appears in Health Connect's permission screen
for JustFitting at all, even on the same APK that shows it fine elsewhere.
Confirmed this is a genuine Health Connect *platform* rollout gap, not a
JustFitting bug -- history reads depend on the installed Health Connect
app/module version per device, and Google ships exactly this check for apps
to use: `HealthConnectFeatures.getFeatureStatus(FEATURE_HEALTH_DATA_HISTORIC_READ)`
(present, though `@ExperimentalFeatureAvailabilityApi`, in this project's
pinned `connect-client:1.1.0-alpha08`). Planned: `HealthConnectBridge.kt`
gains a check using that API; `HealthSyncPlugin.isAvailable()` reports it
alongside its existing SDK-availability fields; `app.js` finally calls
`healthSync.checkAvailability()` (exported since Phase 7.3 but never
actually invoked) and threads the result into `renderHealthSyncStatus`
(`views.js`) so the Account view tells the user directly when their
device's Health Connect can't support history reads yet, instead of the
toggle just silently being missing.

### Roadmap continuation — Phases 8-11 (v3.1/v4.0 done; v5.0 → v5.1 planned)

`things-to-improve.txt` was reorganized into two categories after a
third round of beta-testing: "Good improvements" and "Small Features to
add" (small, mostly-independent fixes) and "Big Remaining Features"
labeled GAME CHANGER (1)/(2)/(3) (larger, structural additions, listed
in the note itself out of numeric order — (1), then (3), then (2)). The
four phases below schedule all of it across four releases, in the
requested order: **v3.1** ships the two small goal-editing fixes first
(lowest risk); **v4.0** ships GAME CHANGER (1) together with the one
small feature explicitly gated on it; **v5.0** ships GAME CHANGER (2)
and (3) together; **v5.1** closes out the four remaining small features.
**Phases 8 (v3.1) and 9 (v4.0) are done; Phases 10-11 are still plans, not
retrospectives**, unlike every "(done)" phase above.

### Phase 8 — Beta-testing feedback, round 3 (part 1): goal-editing correctness (done, v3.1)

Source: `things-to-improve.txt`'s "Good improvements" section — two
goal-plan correctness issues found from real usage, both narrower and
lower-risk than the Game Changer features below, so they ship first.

#### Phase 8.1 — Retroactively editable goal start date (done)

Problem: `GoalPlanManager.create_goal_plan` always stamped a new goal's
`start_date` as `date.today()` unless a caller explicitly overrode it
(only `UserManager.register`'s `goal_start_date` param did, for demo
seeding) — and since Phase 5.3, `GoalPlanManager.active_period_start`
uses the active goal's `start_date` to scope every computed
series/chart/alert/projection to "this goal's own period" once an
account has ever changed goals. A user who was already mid-cut or
mid-bulk before adopting JustFitting — syncing or importing weeks of
pre-existing history — had no way to tell the app their *current* goal
actually started earlier than the day they set it up in the Plan tab;
every goal always started "today," silently excluding real, already-logged
history from that goal's own trajectory/adherence/forecast.

- A new `GoalPlanManager.update_start_date(user_id, new_start_date)`
  mutates the **currently active** goal's `start_date` in place (not a
  new historized row — this corrects when the same goal actually began,
  it isn't a goal change) and records an audit-log entry
  (`start_date: <old> -> <new>`), then
  `metrics_cache.invalidate_for_user(user_id)`, same as every other goal
  mutation.
- Bounds: `new_start_date` must be on or before today (no backdating into
  the future) and, if a previous historized goal exists, strictly after
  that goal's own `start_date` (the goal with the latest `start_date`
  among every *other* goal the account has ever had) — so the two
  periods can't overlap once `active_period_start` scoping applies.
- Only the *active* goal's start date is editable — a historized
  (inactive) goal's `start_date` stays frozen, since perturbing it would
  retroactively change where an already-superseded period's scoping
  boundary was.
- New `PUT /api/users/me/goals/active/start-date` route; the Plan tab's
  "Current plan" section gains an always-visible "Edit start date"
  control (an account always has an active goal, even a brand-new
  default one), a date input constrained (`min`/`max`) to the bounds
  above, pre-filled with the active goal's own `start_date`.
- No schema change (`start_date` already exists on `goal_plans`) and no
  `ENGINE_VERSION` implication — this only changes which already-logged
  rows `active_period_start` includes, not any formula.

#### Phase 8.2 — Reject incoherent target-BF/weekly-rate combinations (done)

Problem: neither `GoalPlanManager.create_goal_plan` (only checked
`0 < target_bf < 1`) nor `GET /api/plan/preview` (no bound at all beyond
whatever `compute_row` happened to raise) ever compared a candidate goal
against the account's *current* body fat — a user could set, say,
`target_bf=0.15` while their latest computed body fat was `0.20` (a "lose
fat" target) paired with a positive `weekly_rate` (a literal gaining
rate), and it was accepted silently.

- A new pure function, `GoalPlanManager.check_goal_coherence(current_bf,
  target_bf, weekly_rate)`, run from both `GoalPlanManager.create_goal_plan`
  (before committing, via a new optional `current_bf` parameter) and
  `GET /api/plan/preview` (so the Plan tab's preview surfaces it before
  commit, not after): `target_bf < current_bf` requires `weekly_rate <=
  0`, `target_bf > current_bf` requires `weekly_rate >= 0`; `target_bf`
  within a small epsilon (`BODY_FAT_COHERENCE_EPSILON`, 0.5 percentage
  points) of `current_bf` allows any rate (maintenance/recomp).
  `current_bf=None` (no computable log yet, e.g. a brand-new default
  goal) skips the check entirely.
- `current_bf` is the account's real latest computed body fat, sourced
  differently in each caller: `PUT /api/users/me` (`user_routes.py`)
  computes it via `MetricsSeriesService.compute_series_for_user` only
  when a `target_bf`/`weekly_rate` change is actually part of the
  request; `GET /api/plan/preview` gets it for free from the candidate
  `compute_row` result it already computes -- `body_fat` never depends
  on `target_bf`/`weekly_rate` (see "The Composition Model" above), so
  that result's `body_fat` *is* the real current figure regardless of
  the candidate params it was computed against, no second engine call
  needed.
- This checks **sign coherence only** — magnitude bounds for a bulk rate
  are already `bulk_rate_out_of_range`'s job (Phase 3), and this phase
  doesn't add an equivalent cut-side magnitude check (see Phase 11.4
  below for that).
- `create_goal_plan`/`update_profile` raise a `GoalPlanManagerError`
  (400) with a plain-language message; `GET /api/plan/preview` returns
  the same message inline after computing the candidate row, instead of
  only failing if the mismatch happens to also trip a
  `ZeroDivisionError`/domain error deep in `compute_row`. The Plan tab's
  existing generic form-error handling (unchanged) renders it as a clear
  inline validation error next to the preview form.
- No schema/engine change — pure validation logic in
  `GoalPlanManager`/`user_routes.py`/`plan_routes.py`.
- New coverage: `GoalPlanManager_test.py` (the coherence function directly,
  `create_goal_plan`'s new `current_bf` param, and `update_start_date`'s
  bounds/audit/cache-invalidation), `Api_test.py` (the new start-date
  route's happy path and every rejection, `PUT /api/users/me` and
  `GET /api/plan/preview` both rejecting/allowing goals against a seeded
  account's real body fat), and a new `client/test/browser/Plan_test.py`
  (Playwright: the start-date control's default value, native
  `max`-date validation, a persisted edit, and the preview form's inline
  error for an incoherent goal).

### Phase 9 — Big remaining features: body composition logging separation (GAME CHANGER 1) + expanded body measurements (done, v4.0)

Source: `things-to-improve.txt`'s "Big Remaining Features" — GAME CHANGER
(1), plus Small Feature 5, which the note itself gates on GAME CHANGER
(1) shipping first ("when big body log separation update is done"). The
largest data-model change since Phase 3.3's daily/weekly coexistence:
perimeters (waist, neck, and — from 9.3 — nine more record-only
measurements) stop being a value required on the same row as
weight/intake/steps and become their own **sporadically-logged** record,
held static from one measurement to the next for every computation in
between, fully decoupled from the weight/nutrition/steps logging cadence.

#### Phase 9.1 — `body_measurements` table and the "static until next update" resolution layer (done)

This sub-phase is pure plumbing — no new UI, foundational for 9.2:

- New table, `body_measurements` (`measurement_id, user_id, date,
  waist_cm, neck_cm, created_at`, `UNIQUE(user_id, date)`, indexed on
  `(user_id, date)` like `body_logs`) — since this project has no
  migration runner yet (Phase 10.1), 9.3's nine extra record-only columns
  were added to the same `SCHEMA` edit rather than a second one, with no
  behavior difference: nothing reads them until 9.3's Quick/Full form
  ships. `body_logs.waist_cm`/`neck_cm` are **dropped** — perimeters are
  no longer a `body_logs` field at all, addressed exclusively through this
  new table going forward. (This specific column removal is exactly the
  kind of change that motivates Phase 10.1's migration protocol — see
  that phase's backfill-migration note for how a real device's existing
  data survives this.)
- A new resolution step, ahead of the engine: given a target date, "the
  most recent `body_measurements` row with `date <= target date`"
  supplies `waist_cm`/`neck_cm` — implemented as
  `BodyMeasurementManager.get_effective(user_id, date)`, called by
  `MetricsSeriesService.compute_series_for_user` (and the
  `plan_routes.py`/`projection_routes.py` engine-input builders, per
  Phase 7.6's lesson that every engine-input site needs to agree) to
  populate `LogInput.waist_cm`/`neck_cm` before `is_computable`/
  `compute_row` ever run. If no measurement has ever been logged for an
  account, resolution returns `None` for both — the week stays
  not-computable, the same "not enough data yet" outcome as today, just
  gated on a different table.
- `CompositionEngine.REQUIRED_FOR_COMPUTATION`/`validate_log_input`/
  `require_complete_log_input` are unchanged in shape (still five
  required fields) — only where `waist_cm`/`neck_cm` come from changes,
  entirely outside `compute_row` itself, so **no `ENGINE_VERSION`
  bump**: the formulas and every value they produce for a given
  `(weight, waist, neck, intake, steps)` tuple are byte-for-byte
  identical to before.
- Cache invalidation gets a new trigger: today,
  `metrics_cache.invalidate_for_user` only runs on a goal/settings change
  or a `body_logs` edit tied to a specific `log_id`. A new/edited
  `body_measurements` row can silently change the resolved input for
  every week between its date and the next measurement's date, none of
  which necessarily touch `body_logs` at all — so
  `BodyMeasurementManager.create`/`update`/`delete` all call the existing
  (already user-scoped, not log-scoped)
  `metrics_cache.invalidate_for_user(user_id)`, the same blunt-but-safe
  pattern Phase 1.5's settings changes already use.
- Export/import: `GET /api/users/me/export` gains a `body_measurements`
  array alongside `logs`; `POST /api/users/me/import` accepts it the same
  way. **Backward compatibility for pre-Phase-9 export files** (which
  still carry `waist_cm`/`neck_cm` inline on each `logs[]` row): the
  import route detects inline perimeter fields on a log entry and,
  instead of discarding them, synthesizes a `body_measurements` row at
  that log's date from them (skipping a date collision the same way
  `logs` import already does) — so restoring an old backup doesn't
  silently lose every historical perimeter reading.
- `Projection.py`'s waist/neck trend-fit source moves from the (now
  perimeter-less) `body_logs` history to `body_measurements` history — a
  strictly sparser, irregularly-dated series, which the existing
  OLS/recency-weighted fit already handles fine (it fits against real
  dates, not a week index). A new `MeasurementPoint` value object carries
  it through `project_series_with_inputs`; fewer than two real
  measurements falls back to holding the last resolved waist/neck
  constant for every forecasted week (there's nothing yet to fit a trend
  against), rather than erroring.
- New/extended test coverage: a new `BodyMeasurementManager_test.py`
  (CRUD, validation, `get_effective`'s static-until-next-update rule,
  audit entries, cache invalidation); `DB_test.py` gained
  `BodyMeasurementDAO` CRUD/cascade-delete cases; `LogManager_test.py`/
  `LogResampler_test.py`/`MetricsCache_test.py` had `waist_cm`/`neck_cm`
  removed from their `BodyLog`/`LogInput` fixtures (a couple now build a
  `LogInput` directly with waist/neck filled in, since those specific
  tests aren't exercising the resolution layer itself); `LogResampler_test.py`
  gained a `ResolveMeasurementsTest` for the new resolution helper;
  `MetricsSeriesService_test.py` gained a case proving a sporadic
  measurement stays effective for later weight-only weeks;
  `DemoSeeder_test.py` now seeds measurements too and checks the seeded
  data resolves to the README's own Demo_cut worked example figures at the
  last logged date; and `Api_test.py` had `waist_cm`/`neck_cm` removed
  from every `/api/logs`(`/by-date`) payload across ~30 tests, with a
  `POST /api/body-measurements` call added wherever a test's assertions
  depend on a computable week. 376 server tests green.

#### Phase 9.2 — Separate "Body" tab; Log wizard drops perimeters (done)

- New nav destination, "Body" (alongside Dashboard/Log/Plan/Alerts/
  Report/Settings/Account in the hamburger menu), backed by a new
  `POST`/`GET`/`PUT /api/body-measurements` route set
  (`body_measurement_routes.py`) — deliberately separate from
  `/api/logs`, matching the note's "separate logging tab" ask directly,
  not a mode within the existing Log view.
- The Body view: a simple date-picker (defaults to today, same navigator
  affordance style as the Log view) plus a two-field form (Waist, Neck)
  and a save button — no wizard needed at only two fields. A history
  table below lists every past measurement (date, waist, neck) — the
  sporadic-record analogue of the Log view's table.
- The **Log wizard drops its Perimeters step** — down to 3 steps (Date &
  weight → Energy → Review) instead of 4; `weight_kg` now sits alongside
  `intake_kcal`/`steps`/`cardio_kcal`/macros on the same cadence, exactly
  matching the note's "weight is separated and needs to be logged daily
  or weekly as nutrition and steps." `LOG_WIZARD_STEPS` drops from 4 to 3
  in `app.js`; step 2's old perimeter fields are removed, not hidden.
- Dashboard's existing Waist/Neck perimeters chart is repointed from the
  current `GET /api/logs` + `GET /api/metrics/series` merge (the exact
  "known limitation" this README already documents above, which this
  phase incidentally resolves for perimeters specifically — steps stays
  the only chart still affected by that limitation) to the new
  `GET /api/body-measurements` endpoint directly, since perimeters are no
  longer resampled/weekly at all. Because the data is now genuinely
  sporadic (irregular gaps between real measurements, "static in
  between" by design), the chart renders as a **held/step line** rather
  than the diagonally-interpolated line every other chart uses — a new
  `charts.js` primitive, `drawStepLineChart` (flat segments between
  consecutive real points, no diagonal interpolation), visually
  communicating "this value didn't actually change, we just haven't
  measured again yet" rather than implying a linear glide between two
  distant readings.
- The 4.3 Dashboard forecast toggle's waist/neck overlay
  (`estimated_waist`/`estimated_neck`) is unaffected in shape —
  `GET /api/projection` still returns those fields, just sourced from
  9.1's relocated trend-fit; the Dashboard appends them as trailing
  projected points onto the same step-line chart, still marked hollow
  like every other chart's forecast points.
- No manual `sw.js` cache bump needed — Phase 5.1's self-hashing service
  worker already picks up every edit here automatically.
- New/extended test coverage: `Log_test.py`/`Dashboard_test.py`/
  `Plan_test.py`/`Views_test.py` (Playwright) updated for the 3-step
  wizard flow and the Body view; the retired perimeter-prefill test
  removed (that Phase 5.4 behavior no longer exists once perimeters left
  the Log wizard); `renderLogTable`'s shifted column indices; two new
  `Views_test.py` cases for `renderBodyMeasurementTable`'s carry-forward
  behavior and `fillBodyMeasurementForm`. Also caught and fixed two real
  bugs along the way, both the same navigate()-races-an-unawaited-refresh
  shape already fixed for the Account/Settings views (see their own
  notes above and v2.0.1's CHANGELOG entry) — fixed the same way in both
  cases, by reordering the local, no-network-dependency reset to run
  synchronously before the async fetch instead of after it:
  - Navigating to the Body view fired an unawaited `refreshBody()` whose
    form-defaults reset (including the date input) could land *after* a
    fast-typing user had already started filling the form, silently
    clobbering it.
  - `refreshLogs()` — called unawaited from `navigate("log")` since
    before Phase 9 existed — ran `goToLogStep(1)` *after* its own fetch,
    so a late-resolving fetch could reset an in-progress wizard back to
    step 1 mid-entry, hiding `#log-save` right as something tried to
    click it. This one wasn't caught locally at all — it only surfaced
    as two Playwright timeouts on CI (a slower/more loaded runner than
    local dev), reproduced afterward by throttling the API locally to
    confirm the fix. Narrowed into actually landing by this same phase's
    own changes: the Log wizard shrinking to 3 steps, and the new Body-
    tab round trip most tests now need before logging a computable week,
    both meaningfully shrink the real time available before the race
    window closes on its own.

  376 server tests, 66 client tests green.

#### Phase 9.3 — Expanded body measurements (Small Feature 5) (done)

- `body_measurements` gains nine more nullable columns, all
  **record-only, never read by `CompositionEngine`**: `shoulder_cm,
  chest_cm, hips_cm, biceps_r_cm, biceps_l_cm, thigh_r_cm, thigh_l_cm,
  calf_r_cm, calf_l_cm` — the exact list from the note.
- The Body view's form gains a **Quick / Full** toggle, matching the
  note's "user can only log (waist and neck) or (all measurements)"
  constraint exactly (not an arbitrary field-by-field subset): Quick
  submits only waist/neck (9.2's existing form, unchanged); Full reveals
  all eleven fields. A Full entry leaves any field the user didn't fill
  in as `NULL` for that specific date's row — the history table (and any
  future chart of a non-computational measurement) resolves a blank cell
  the same "most recent non-null value as of this date" way 9.1 already
  established for waist/neck, so e.g. a Quick entry between two Full
  entries doesn't make Chest/Hips *appear* to reset to blank, it just
  means that date's own row didn't touch them.
- `BodyMeasurementDTO` and the JSON export/import contract extend to the
  full eleven-field column set (`GET /api/users/me/export`'s
  `body_measurements` array, `POST /api/users/me/import`'s matching
  key — see `docs/import_format.md`); the nine new fields are always
  optional on import, so a pre-Phase-9.3 export file (which won't have
  them at all) still imports cleanly. Deliberately **not** extended to
  CSV: the Account view's CSV import path only ever produces `{"logs":
  [...]}` (`csvImport.js`), and there's no case for a second CSV pipeline
  just for a record-only, low-volume field set the JSON path already
  covers.
- No new alerts, no chart beyond the history table for now — purely a
  record-keeping feature, per the note's own "do not intervene in
  computations."

### Phase 10 — Big remaining features: DB migration protocol (GAME CHANGER 2) + Today dashboard section (GAME CHANGER 3) (planned, v5.0)

Source: `things-to-improve.txt`'s GAME CHANGER (2) and GAME CHANGER (3) —
listed in the note itself out of numeric order (3 appears before 2);
grouped together here per the requested v5.0 pairing. Deliberately
sequenced after Phase 9 (v4.0): 10.1's migration protocol is far more
concretely motivated with a real, already-shipped schema change (Phase
9's `body_logs.waist_cm`/`neck_cm` removal) to design a backfill
migration against, rather than being built speculatively with nothing yet
to migrate.

#### Phase 10.1 — Versioned DB migration protocol (planned)

Problem: `DB.py`'s own docstring is explicit that this project keeps "no
real user data that a migration history would need to carry forward" —
true when it was written (pre-Android, and the Phase 1.0 squash of what
used to be 19 numbered migrations into one idempotent `SCHEMA` script
happened before Phase 6 gave Android a genuine on-device, persistent
SQLite file). It's no longer true: Phase 6 shipped real on-device
persistence, and by the time Phase 9 ships, real users may have real
accumulated `body_logs`/`goal_plans`/`engine_settings`/`body_measurements`
rows on their phones. `CREATE TABLE IF NOT EXISTS` is a no-op against an
existing file with an outdated schema — it does not add columns, rename
them, or move data — so today's "delete and let it be recreated"
convention (fine for a dev machine or the ephemeral Render demo instance)
would mean an app update **silently fails to pick up the new schema** on
a real device's existing DB, or, worse, a future column removal (exactly
what Phase 9 just did) simply leaves the stale column and stale data
behind untouched, forever, since nothing runs to reconcile it.

Plan:
- Bring back a real migration runner — a return to the
  pre-Phase-1.0-squash design, this time justified by data that actually
  needs to survive. SQLite's own `PRAGMA user_version` (a plain integer
  already stored in the DB file header) tracks the applied version, no
  new table required.
- New `server/src/data/db/migrations/` package, one module per version
  (`m0001_baseline.py`, `m0002_...`, ...), each exposing
  `upgrade(conn: sqlite3.Connection) -> None`. `DB.__init__` reads
  `PRAGMA user_version`, applies every migration numbered above it in
  order inside one transaction (so a failure never leaves a
  half-migrated file), then sets `PRAGMA user_version` to the latest
  applied number. Migration 1 is a no-op "this is the current `SCHEMA` as
  of this phase" baseline, so a brand-new DB (dev machine, fresh Android
  install, a fresh Render deploy) and an upgraded existing DB converge on
  an identical end state.
- SQLite can `ADD COLUMN`/`RENAME COLUMN`/`RENAME TABLE` natively but has
  no `DROP COLUMN` before 3.35 and no `ALTER COLUMN TYPE` at all — a
  migration doing either needs the standard "create new table, copy data
  across, drop old, rename" sequence. This directly matters for the one
  schema change already in the plan ahead of this phase: **a "catch-up"
  migration is needed for any real device that installed the Phase 9
  (v4.0) release before this migration protocol (v5.0) existed** — it
  must copy any surviving `body_logs.waist_cm`/`neck_cm` values (if that
  device's data predates even Phase 9's own dev-time schema edit) into
  `body_measurements` rows before dropping the columns, mirroring Phase
  9.1's own JSON-import backfill logic but as a migration instead of a
  manual import.
- `scripts/reset_db.sh`/`seed_demo_data.sh` and `DB.py`'s docstring get
  rewritten for the new convention: a schema change from here on is a new
  migration file, not a `SCHEMA` edit; local dev may still reset for
  convenience (faster than writing a migration while iterating), but a
  real device always migrates in place, never resets.
- No `ENGINE_VERSION` implication — this is a persistence-layer
  mechanism, unrelated to `CompositionEngine`'s own cached-snapshot
  versioning.
- New `DB_test.py` migration-runner coverage: applying every migration in
  order against a fixture DB seeded at each historical version reproduces
  a fresh install's schema and preserves existing data, plus specifically
  exercising the `body_logs`→`body_measurements` catch-up migration's
  backfill.

#### Phase 10.2 — Today dashboard section (planned)

Problem: the Dashboard only ever shows the last **computed, complete**
week. Since Phase 7.3-7.6's Health Connect sync, a user can have real
steps/nutrition data for *today* sitting in a partial `body_logs` row
(Phase 7.4) with nowhere on the Dashboard that surfaces it before the
week closes and the row becomes computable.

Plan:
- A new "Today" stat-row, the first section on the Dashboard (above
  Weight & Body Composition), backed by a new thin
  `GET /api/logs/by-date/<date>` route (the read-side counterpart to
  Phase 7.4's existing `PUT /api/logs/by-date/<date>`, both wrapping
  `LogManager.get_by_date`).
- Tiles: **Steps done** (today's `steps`, dash if not yet synced/logged),
  **Kcals eaten** (today's `intake_kcal`, dash if unset), **Kcal to
  target** (`target_calories - intake_kcal`, only rendered once both are
  known), and a combined **TEF / NEAT / EAT today** block.
- Today's own row is essentially never `is_computable` (per Phase 9's
  design, it won't have its own waist/neck, and typically won't yet have
  a full week's worth of anything else either) — so these figures can't
  come from a persisted `compute_row` result. They're an **estimate**,
  generalizing Phase 9's "hold the last known value" idea from perimeters
  to lean mass/BMR: NEAT recomputed from today's real `steps` against the
  most recent computed week's `lean_mass_kg` (held static), TEF from
  today's real macros (or the flat estimate) against today's real
  `intake_kcal`, EAT straight from today's real `cardio_kcal`. Computed
  on the fly in a new read-side module (`services/composition/
  TodayEstimate.py`, alongside `GainQuality.py`/`EnergyReconciliation.py`'s
  existing "derived view over an already-computed series" pattern) —
  never persisted to `metrics_snapshots`, no `ENGINE_VERSION` implication,
  same "computed but not cached" precedent `GET /api/plan/preview`
  already established.
- **"Incomplete/current" framing is inferred, not stored** — consistent
  with this project's consistent preference for a derived property over a
  new column (`GoalPlan.direction`, the `unconfigured_goal` alert): a row
  counts as "current" precisely when `date == today` and
  `not LogResampler.is_computable(row)` (or no row exists for today at
  all). The Today section renders that state as a badge; no new
  `body_logs` column, no lifecycle to manage — it stops being "current"
  automatically the moment either the day rolls over or the row becomes
  complete.
- **Daily step / cardio goals**: a new goal type, independent of the main
  `GoalPlan`/Plan tab per the note's own wording ("planned in a similar
  way to the main goal plan but independently") — a new `activity_goals`
  table (`activity_goal_id, user_id, steps_goal, cardio_kcal_goal,
  start_date, active, created_at`), historized the same
  create-new/deactivate-old/audit pattern as `GoalPlanManager`, in a
  parallel `ActivityGoalManager`, with `GET`/`PUT
  /api/users/me/activity-goal` routes. Unlike the body-fat goal, there's
  no cut/bulk-direction coherence check to port over (steps/cardio have
  no sign relationship to body fat). Once set, the Today section's tiles
  gain "Steps left today"/"Cardio left today"; unset by default, matching
  Phase 5.2's "don't force a goal at signup" precedent — no onboarding
  step forces this.

### Phase 11 — Beta-testing feedback, round 3 (part 2): remaining small features (planned, v5.1)

Source: `things-to-improve.txt`'s remaining four "Small Features to add"
items — the same four the Phase 7 section above originally
forward-referenced as "Phase 8"; renumbered to Phase 11 now that Phases
8-10 sit ahead of them, matching the requested v3.1 → v4.0 → v5.0 → v5.1
sequencing.

#### Phase 11.1 — Goal progress bar on the Dashboard (planned)

- A full-page-width progress bar (respecting the page's existing
  margins, per the note) placed just above the chart grid, spanning
  `[active goal's start_date, today + current weeks_to_goal]` with today
  marked as the filled portion. The right edge is a **moving target** —
  it's recomputed from the live `weeks_to_goal` on every dashboard load,
  so it can shift week to week as real adherence data comes in, the same
  way `weeks_to_goal` itself already behaves as a receding-horizon figure
  elsewhere in the engine (see the Composition Model section above) —
  documented as deliberate, not a bug.
- Purely client-side: a new `views.js` `renderGoalProgressBar` (a
  lightweight DOM/SVG element, not a `charts.js` data-series primitive)
  fed by `GET /api/users/me/goals` (active goal's `start_date`) and
  `GET /api/metrics/latest` (`weeks_to_goal`) — both already fetched by
  `refreshDashboardSummary`. No server/API/DB change, no
  `ENGINE_VERSION` implication, the same "every figure already exists"
  precedent Phase 4.2/4.3/5.5/5.6 all followed.

#### Phase 11.2 — "Last logged" info line (planned)

- A small subtitle, e.g. "Last logged: 3 days ago (2026-07-07)", derived
  client-side from the max date already present in `state.logs` (or
  `GET /api/metrics/latest`'s own date) — placed near the new Today
  section (Phase 10.2) or under the Weight & Body Composition heading. No
  new endpoint.

#### Phase 11.3 — Missing-log alert (planned)

- A new detector, `stale_log`, in `Alerts.py`, following the established
  pattern (a new per-account-overridable `missing_log_alert_days` field
  on `EngineConstants`/`EngineSettings`, default `7`) — fires when
  `today - <latest real log's date>` exceeds the threshold (or since the
  goal's `start_date` if the account has never logged at all).
- This is the **first** alert detector that depends on wall-clock "now"
  rather than purely comparing already-logged rows against each other —
  every existing detector (implausible-change, stagnation, deviation,
  etc.) only ever looks at data that's already been logged.
  `AlertSyncService.sync_alerts` gains an explicit `today` parameter
  (defaulting to `date.today()`, injectable for tests) threaded through
  to this one detector.
- Persisted/dismissed through the existing `alert_log` pipeline, deduped
  on `(user_id, type, date)` like every other alert — since `date` here
  is "today," dismissing it only silences *today's* firing; it can
  re-fire (and be re-dismissed) again tomorrow if the account is still
  stale, rather than a persistent one-time nag. This is the simplest fit
  for the existing dedup key, not a new snooze mechanism.

#### Phase 11.4 — Excessive cut-rate alert (planned)

- A new goal-level detector, `cut_rate_out_of_range`, the direct
  structural mirror of Phase 3's existing `bulk_rate_out_of_range`: for
  `goal.direction == "cut"`, fires when
  `abs(weekly_rate) > MAX_CUT_RATE_PCT` (a new module constant in
  `constants.py`, default `0.01` — the literature-cited "max ~1%/week of
  bodyweight" figure the note cites, to avoid inducing excess muscle
  loss).
- Mirrors `bulk_rate_out_of_range` exactly in scope, including staying a
  **fixed module constant**, not a per-account-overridable
  `EngineSettings` field — `BULK_RATE_MIN`/`BULK_RATE_MAX` aren't
  overridable today either, so this keeps both sides of the same check
  consistent rather than promoting only the new one. (Promoting both to
  per-account settings together would be a reasonable future consistency
  cleanup, out of scope here.)

**With Phase 11, every item from `things-to-improve.txt`'s three rounds
of beta-testing feedback (Phases 4, 5, and this 8/9/10/11 continuation)
will be scheduled.**

## Android app

JustFitting ships as an installable Android app by bundling the static
web client **inside** the APK using [Capacitor](https://capacitorjs.com/),
rather than opening a hosted URL through a browser wrapper. Since Phase 6
(below), the Android app also bundles and runs its own copy of the Flask
API and SQLite persistence on-device, reachable only at `127.0.0.1` — the
web deployment (GitHub Pages + Render) is the only build target that
still talks to a remote API. No native UI rewrite either way: both are
the same web client, just pointed at a different API base URL per build
target.

```
scripts/build_static_site.py <API_URL>   # same build the web deploy uses
        |
dist/  (HTML/CSS/JS, api_base_url baked into index.html)
        |
capacitor.config.json  (webDir: "dist")
        |
npx cap sync android    # copies dist/ into the native Android project
        |
Android app: local UI + (since Phase 6) an embedded Flask/SQLite server
             reachable only at 127.0.0.1 -- see "Embedded on-device
             server" below. <API_URL> above is 127.0.0.1 by default now;
             a remote URL is only used for the emulator/LAN dev workflow.
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
`api.js`) — just a different target URL per case. **Web** and
**Android** are genuinely different targets now (Phase 6): the web
deployment still points at a remote API; the Android app's default
target is its own embedded, on-device server.

| Target | Command |
| --- | --- |
| Web deployment (production, remote API) | `python scripts/build_static_site.py https://YOUR_PRODUCTION_API_URL` — what the release workflow bakes in for GitHub Pages; not used for Android |
| **Android app (default, since Phase 6)** | `python scripts/build_static_site.py http://127.0.0.1:5000` — also `npm run build:web:android`, what `npm run android:sync`/`android:apk` use by default |
| Android emulator, debugging the client against a desktop-run server | `python scripts/build_static_site.py http://10.0.2.2:5000` (the emulator's alias for the host's `localhost`) — also `npm run build:web:android-remote-dev` |
| Real device on the same LAN, same purpose | `python scripts/build_static_site.py http://LOCAL_MACHINE_LAN_IP:5000` |

The last two are a **development-only workflow**: iterating on client UI
against a desktop-run `python -m server.src.Server` without rebuilding
the whole Chaquopy-bundled APK on every change. They're never what
actually ships — the embedded target is.

```bash
npm run android:sync             # default: build:web:android (embedded) + `npx cap sync android`
npm run android:sync:remote-dev  # dev-only: build:web:android-remote-dev (emulator/LAN) + sync
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
bundled `dist/` before rebuilding — the default target is the embedded
server (`http://127.0.0.1:5000`), which is what a release build should
ship too; `npx cap sync android` alone (without re-running the `build:web:*`
step) just re-copies whatever `dist/` was last built for. For an actual
Play Store release, build a signed AAB/APK (`gradlew.bat bundleRelease`
or Android Studio's Build menu, with a real keystore — not covered here).

### Network notes

- **The web deployment must use HTTPS.** `scripts/build_static_site.py`'s
  production target and `capacitor.config.json`'s lack of a `cleartext`
  override both assume this — Android's default cleartext-traffic block
  applies to anything not explicitly allowed.
- **The Android app's default (embedded) target needs cleartext allowed,
  but only to itself.** `network_security_config.xml` (Phase 6, below)
  scopes Android's cleartext exception to `127.0.0.1` specifically, wired
  into `AndroidManifest.xml` — no `capacitor.config.json` change needed
  for this, and no other host can ever use cleartext through it.
- **Local HTTP dev (emulator/LAN, the opt-in `:remote-dev` target above)
  needs cleartext enabled explicitly, and differently.** To test against
  `http://10.0.2.2:5000` or a LAN IP with a desktop-run server instead of
  the embedded one, temporarily add `"server": {"cleartext": true}` to
  `capacitor.config.json`, re-run `npx cap sync android`, and **revert it
  before any real build** — never ship `cleartext: true`, and don't
  confuse this dev-only blanket flag with the embedded target's scoped
  XML config above.
- **CORS**: the server reads `JUSTFITTING_CORS_ORIGINS` from the
  environment (`server/src/api/app.py`) instead of hardcoding origins.
  Capacitor's Android WebView serves the bundled UI from the
  `https://localhost` origin by default, so if you lock
  `JUSTFITTING_CORS_ORIGINS` down to an allowlist (rather than the
  default `*`), include `https://localhost` in it. The embedded server's
  own env sets this to `https://localhost` automatically
  (`local_server.py`).

### Status

`android/` is scaffolded and committed (Capacitor's convention, since the
native project holds Gradle/signing/manifest customizations `cap sync`
doesn't regenerate). The full toolchain above — conda-managed Node/JDK,
the command-line SDK tools, and `npm run android:apk` — has been verified
to produce a working debug APK, with no admin rights and no global
environment variables anywhere in the chain. `android/app/build.gradle`'s
`versionName`/`versionCode` now track the repo's own `vX.Y.Z` release
tags (README's Versioning section), having never previously been bumped
past their Phase-2-scaffold defaults (`1.0`/`1`) until Phase 6 moved them
to `2.0.0`/`2`; currently `4.0.0`/`8`, tracking this Phase 9 release. Not
done: a release keystore/signed build, and an emulator system image
(needs admin — use a real device instead, see above).

### Embedded on-device server (Phase 6, done)

**Goal**: the Android app becomes self-contained. When it's opened, it
starts its own copy of `server/src/api/app.py`'s Flask API, listening on
loopback only, backed by a SQLite file living in the app's private
storage — and the exact same client UI Phase 2 already bundles talks to
`http://127.0.0.1:<port>` instead of a remote `JUSTFITTING_API_BASE_URL`.
One app, one process, two logical halves in the same relationship
`scripts/run.sh`'s two terminals have on a dev machine today, just
started together instead of separately.

**Non-goals**: this is not a rewrite of the composition engine, not a
second app, and not a sync/multi-device feature — an on-device account's
data lives only on that device (`GET /api/users/me/report` and
`/export` remain the manual way to move data off it, same as today).

#### Why an embedded Python interpreter, not a JS port

The engine (`server/src/services/composition/`) is the product's actual
value — five phases of carefully derived, cross-checked formulas
(`docs/composition_spec.md`), each with its own golden-reference test.
Reimplementing it in client JS to avoid an on-device server would fork it
into two implementations that must be kept in sync forever, doubling the
regression surface for every future phase. Embedding CPython instead
means the Android app runs the literal same `server/src/` package the
tests already cover — zero engine rewrite, and every existing
`server/test` suite stays the real verification for Android's behavior
too, not just the web/API's.

[Chaquopy](https://chaquo.com/chaquopy/) (a Gradle plugin) is the
concrete mechanism: it bundles a real CPython interpreter plus
pip-installed dependencies into the APK per target ABI, callable from
Kotlin/Java. This project's server dependencies
(`server/requirements-prod.txt`: Flask, flask-cors, python-dotenv,
waitress) are all pure-Python — no C-extension wheels to cross-compile
for Android, which is the usual Chaquopy pain point — so this should be a
comparatively clean integration. This is actually a *return* to the
original Phase 2 plan (Chaquopy + on-device Flask + WebView), which was
repointed to a hosted-API approach (TWA, then Capacitor) before any of it
was built, for simplicity's sake at the time (see CHANGELOG's Phase 2
history). Phase 6 is that same idea, now justified by a real persistence
requirement instead of just "serve the client locally."

**Chaquopy's license, resolved**: [MIT-licensed since v12.0.1](https://chaquo.com/chaquopy/license/)
(this project uses 17.0.0) — free for commercial and closed-source apps,
no royalties, no revenue thresholds, published straight to Maven Central.
No longer a constraint on this project's distribution model.

#### One process, two logical halves (done, verified on a real device)

```
Android app process
├── MainActivity.java (Capacitor's native shell -- Java, not Kotlin;
│   │                   the existing generated project already is Java,
│   │                   so no new language dependency was added)
│   ├── onCreate(): installs the platform SplashScreen (already
│   │   themed via res/values/styles.xml's AppTheme.NoActionBarLaunch,
│   │   Capacitor's own scaffold, previously unused), then starts
│   │   Chaquopy's Python interpreter + local_server.py's
│   │   start(db_path, port) on a background thread, then immediately
│   │   calls super.onCreate() -- the WebView starts loading the bundled
│   │   (fully local) dist/index.html right away instead of waiting
│   │   -> imports server.src.api.app:create_app()
│   │   -> runs it via waitress (same as server/wsgi.py, not Flask's
│   │      dev server) bound to 127.0.0.1:5000
│   │   -> DB_PATH = <app-private files dir>/justfitting.db
│   └── the splash stays on screen (setKeepOnScreenCondition) until that
│       background thread signals ready (verified by
│       android/app/src/main/python/local_server_test.py, a
│       desktop-runnable test against a real socket -- passes), instead
│       of blocking onCreate() itself, which would risk an ANR on a slow
│       device and give the platform's own splash-dismiss timing nothing
│       to actually wait for
└── Capacitor WebView
    └── the same dist/ client Phase 2 already bundles, built with
        JUSTFITTING_API_BASE_URL=http://127.0.0.1:5000 baked in via
        `npm run build:web:android` -- the default target since Phase 6
```

No separate Android Service, no notification, no background execution
after the app is swiped away — the server's lifetime is tied to the
app's process, matching the "two local terminals" mental model exactly:
closing the app stops the server, same as Ctrl+C; reopening it starts a
fresh server process against the same persisted DB file, same as
re-running `python -m server.src.Server`. Verified end-to-end on a real
device (`adb install` + launch): the embedded server binds a real
listening socket on `127.0.0.1:5000`, `GET /api/health` responds
correctly through it, and the WebView performs a full real-account
round trip through it -- registration, logging a week, a real computed
Dashboard, data surviving a force-close/reopen (the actual "persistence
on the phone" promise), and full functionality in Airplane Mode
(confirming it never reaches Render). One real bug surfaced and was
fixed along the way: an initial `chaquopy.sourceSets` configuration used
`include("server/**")` to scope the repo-root source directory, which
crashed the app on launch with `ModuleNotFoundError: No module named
'local_server'` -- a Gradle `SourceDirectorySet`'s include/exclude
patterns apply globally across *every* srcDir registered on it (matched
relative to each srcDir's own root), so that include pattern also
filtered out `local_server.py` from this module's own default
`src/main/python` srcDir, whose relative path there is just
`"local_server.py"`, not `"server/..."`. `assembleDebug` succeeding
didn't catch this -- a source file being silently filtered isn't a build
error. Fixed by dropping the `include(...)` allowlist and using
`exclude(...)`-only patterns instead, which only ever remove matches and
never act as an allowlist against srcDirs they weren't written for.
A second bug surfaced while adding the cold-start splash screen below:
calling `androidx.core.splashscreen`'s `installSplashScreen()` without a
`postSplashScreenTheme` declared crashed the app with `IllegalStateException:
You need to use a Theme.AppCompat theme (or descendant) with this
activity`, since Capacitor's `BridgeActivity` (an `AppCompatActivity`)
checks the active theme in its own `onCreate()`, and without that
attribute the splash-screen library never restores the activity to its
real AppCompat-descended theme. Fixed by adding `postSplashScreenTheme`
to `AppTheme.NoActionBarLaunch` (`res/values/styles.xml`), pointing at
the existing `AppTheme.NoActionBar`.

#### Networking & security

- The server binds **loopback only** (`127.0.0.1`, never `0.0.0.0`) — no
  other app or device on the network can reach it, unlike the LAN-dev
  case the Network notes above describe.
- Android still blocks plaintext HTTP by default (API 28+), so this needs
  a cleartext exception — but scoped precisely to `127.0.0.1` via a
  `network_security_config.xml` (`<domain-config
  cleartextTrafficPermitted="true"><domain>127.0.0.1</domain></domain-config>`),
  instead of today's dev-only blanket `"server": {"cleartext": true}` in
  `capacitor.config.json` (which the Network notes above say to always
  revert before a release build). This is actually *more* precise than
  today's LAN-dev workaround: the exception only ever applies to the
  device talking to itself.
- CORS: `JUSTFITTING_CORS_ORIGINS` is already environment-driven
  (`server/src/api/app.py`); the embedded server's env just needs
  `https://localhost` allowed, the same origin the Network notes above
  already document for Capacitor's WebView.

#### Persistence

- `DB_PATH` resolves to a path under Android's app-private storage
  (`Context.getFilesDir()`), passed into the Python process the same way
  `JUSTFITTING_DB_PATH` already overrides it today — no server code
  change needed, this is purely a native-side config value.
- `DB.py`'s idempotent `CREATE TABLE IF NOT EXISTS` schema (see its own
  module docstring) already applies on every connect with no migration
  runner — an app update that adds columns just works on next launch,
  the same story a `git pull` + restart already is for a dev/prod server.
- Uninstalling the app deletes its data (standard Android sandboxing);
  `GET /api/users/me/export` remains the user's manual backup/move path,
  now genuinely useful for Android since there's no server-side copy to
  fall back on. `android:allowBackup` (`AndroidManifest.xml`) is left at
  Capacitor's own scaffolded default, `true` — a deliberate choice, not
  an inherited one: Android's Auto Backup then includes `justfitting.db`
  in the user's Google account backup, so a phone upgrade/reset restores
  logged data automatically, at the cost of that data (including the
  password hash) leaving the device via Google's backup, not just
  JustFitting's own `/export`.

#### Build & distribution changes

- `android/build.gradle` / `android/app/build.gradle` (**done**): the
  Chaquopy Gradle plugin (`com.chaquo.python:gradle:17.0.0`, resolves
  from plain `mavenCentral()`, no extra repo needed at this version) and
  a `chaquopy { defaultConfig { pip { install ... } } }` block mirroring
  `server/requirements-prod.txt` (a new place that list has to stay in
  sync with — worth a comment pointing each at the other). A
  `chaquopy.sourceSets` entry adds the repo root as a Python source
  directory, `exclude`-only (`client/**`, `scripts/**`, `node_modules/**`,
  `docs/**`, `android/**`, `.git/**`, and a few more, plus
  `server/test/**`/`**/*_test.py`/`**/__pycache__/**` — no `include(...)`
  allowlist, see the bug below for why), so the app imports the literal
  `server.src.*` package from its real location, not a copy. Four
  version-specific gotchas hit and resolved while wiring this up:
  - Chaquopy 17 requires **minSdk >= 24** — `android/variables.gradle`
    bumped `minSdkVersion` `22 -> 24` (drops Android 5.1/6.0 support).
  - Chaquopy's build-time interpreter (`buildPython`, used to resolve
    pip packages, distinct from the on-device runtime) must exactly
    match the app's target Python major.minor. The desktop `justfitting`
    conda env resolves to Python 3.12.13 (not `environment.yml`'s
    `>=3.10` floor), so `chaquopy.defaultConfig.version` is pinned to
    `"3.12"` rather than Chaquopy's own 3.10 default — with `conda
    activate justfitting` run first, plain `python` on `PATH` already
    resolves to the matching interpreter, so no hardcoded
    machine-specific `buildPython(...)` path was needed (same
    session-scoped philosophy as this section's `JAVA_HOME` handling
    above).
  - Chaquopy only ships Python 3.12 for 64-bit ABIs — `ndk.abiFilters`
    narrowed to `arm64-v8a`/`x86_64` (real devices + emulator); the
    32-bit ABIs a broader filter would have requested aren't available
    for this Python version at all, not just unwanted for size.
  - Verified with a real `assembleDebug` run: Flask 3.1.3, flask-cors
    4.0.2, python-dotenv 1.2.2, waitress 3.0.2 and their transitive deps
    (Werkzeug, Jinja2, MarkupSafe, click, itsdangerous, blinker) installed
    cleanly for both ABIs, no C-extension/wheel-availability problems.
- `android/app/src/main/python/local_server.py` (**done**): the on-device
  entry point Chaquopy calls into — see the diagram above. Its own
  desktop-runnable test, `local_server_test.py` (excluded from the
  bundled APK via the `**/*_test.py` exclude above), passes against a
  real socket, confirming the DB file gets created at the given path and
  that a second `start()` call is a true no-op.
- `MainActivity.java` (**done**, plain Java — the existing Capacitor
  project already is Java, not Kotlin, so this needed no new bridge
  language): installs the platform splash screen, starts Chaquopy's
  interpreter and calls `local_server.start(db_path, port)` on a
  background thread, and calls `super.onCreate()` immediately rather than
  blocking on server startup — see the diagram above and the cold-start
  item below. `android/app/build.gradle` gained an explicit
  `compileOptions` (Java 8) for the lambdas this uses, not relying on
  AGP's own default.
- `android/app/src/main/res/xml/network_security_config.xml` (**done**),
  wired into `AndroidManifest.xml`'s `android:networkSecurityConfig`: the
  scoped cleartext exception above.
- `scripts/build_static_site.py`: no code change needed (it already
  takes an arbitrary API base URL) — `npm run android:sync`/`android:apk`
  (**done**) now build the embedded target
  (`http://127.0.0.1:5000`) **by default**, matching what actually ships;
  the previous emulator/LAN-pointed behavior moved to explicitly-named
  `npm run android:sync:remote-dev`/`build:web:android-remote-dev`
  scripts rather than being removed, since it's still useful for
  iterating on client-only changes without rebuilding the whole
  Chaquopy-bundled APK each time.
- `environment.yml`: no new conda dependency for the on-device runtime
  itself — Chaquopy downloads its own Android-ABI Python build via
  Gradle, separate from the desktop `justfitting` conda env. That conda
  env is still needed at Android build time now, though, for its
  matching-version `python` (`buildPython`, above) and its JDK
  (`JAVA_HOME`, already true before Phase 6) — both session-scoped via
  `conda activate justfitting`, not a new persistent dependency.

#### What stays exactly the same

- The web deployment (GitHub Pages client + Render API, `render.yaml`,
  the release workflow) — a completely untouched build target.
- The composition engine, every DAO/service, every existing
  `server/test`/`client/test` suite — Android runs the identical Python
  package, not a port.
- The client JS (`api.js`, `session.js`, `views.js`, `app.js`,
  `charts.js`) — it already only knows "some base URL," never how that
  URL is reached.

#### Open risks to validate before/while building this

- **APK size**: the debug build grew from the pre-Chaquopy baseline's
  ~4.1 MB (`JustFitting-debug-v1-2.apk`) to ~40.8 MB with both
  `arm64-v8a` and `x86_64` bundled in one APK (a real device only ever
  uses one ABI's worth of native libraries at runtime, so this
  single-APK debug number overstates what an actual install needs).
  Release-mode ABI splitting (Gradle APK splits, or an Android App
  Bundle, which the Play Store already does automatically) would shrink
  this — explicitly **out of scope**: not a concern for this project
  right now.
- **Cold-start time** — **resolved**: `MainActivity.onCreate()` no
  longer blocks on server startup. It installs the platform splash
  screen (`androidx.core.splashscreen`, already themed via Capacitor's
  own `AppTheme.NoActionBarLaunch` scaffold, previously unused), starts
  Chaquopy + `local_server.py` on a background thread, and calls
  `super.onCreate()` immediately — the WebView starts loading the
  bundled (fully local) shell right away, while the splash stays up
  (`setKeepOnScreenCondition`) until the server signals ready. Verified
  on the real device: launches cleanly, no ANR risk from a blocked main
  thread. One bug found and fixed getting here — see above
  (`postSplashScreenTheme` / `IllegalStateException`).
- **Chaquopy licensing** — **resolved**: [MIT-licensed since v12.0.1](https://chaquo.com/chaquopy/license/),
  free for commercial/closed-source use, no royalties. See above.
- **Dependency wheel availability** for Flask/Werkzeug/Jinja2/click/
  itsdangerous/flask-cors/waitress on Chaquopy's supported Android ABIs —
  **resolved**: confirmed clean (no C-extension/wheel problems) via a
  real `assembleDebug` run, see above.
- **`npm run android:sync`/`android:apk` building the wrong target by
  default** — **resolved**: they now build the embedded target, matching
  what actually ships; see Build & distribution changes above.
- **End-to-end device verification** — **resolved**: installed
  (`JustFitting-debug.apk`, repo root) on a real phone via `adb install`.
  First attempt crashed on launch (`ModuleNotFoundError: No module named
  'local_server'`, root-caused and fixed — see above); after the fix, the
  app launches, the embedded server binds and answers `/api/health`
  through a real socket, and a full account round trip (register, log a
  week, view the computed Dashboard, force-close and reopen with data
  intact, works fully in Airplane Mode) all checked out on the device —
  reconfirmed after the cold-start and default-script changes too.

Status: **done.** Every piece — the Gradle/Chaquopy plumbing, the
`server/src` sourceSet wiring (including the include/exclude bug found
and fixed), `local_server.py`, the `MainActivity.java` bridge and its
cold-start splash screen, the scoped network security config, and the
embedded-target build scripts (now the default) — is built and verified
end-to-end on a real Android device. Chaquopy's license is confirmed
compatible with this project's distribution. `android/app/build.gradle`'s
`versionName`/`versionCode` are bumped to `2.0.0`/`2`. The one item left
on the table is APK size via release-mode ABI splitting, deliberately out
of scope for now.

### Alternative considered: client-side local/offline mode (design note, superseded by Phase 6)

Before Phase 6, the fallback design for "make the Android app not depend
on network access" was a data-access layer inside the client JS choosing
between **remote API mode** (today's behavior), **local storage mode** (a
Capacitor storage/SQLite plugin caching or accepting offline entries),
and a future **sync mode** reconciling the two — deliberately avoiding an
on-device server. Phase 6 replaces this direction: persistence needed a
real reason to justify embedding Python, and "the app should work
standalone with real persistence" is that reason. This note stays on
record as the fallback if Chaquopy turns out to be impractical (APK size,
licensing) — the same three-mode JS data-access-layer idea would then be
the way to get offline support without an embedded server.

## The Team

Demo_cut Arias — University of Deusto, Bilbao.
