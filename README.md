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
│   │   └── webapp/{templates,static/{css,js}}
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

### Phase 1.1 — Data model & audit hardening

- Split `GoalPlan` out of `UserProfile` into its own historized entity
  (`goal_id, user_id, target_bf, weekly_rate, start_date, active`), so a
  user's goal history survives across changes instead of being
  overwritten in place.
- Add an audit trail for `BodyLog`/profile/goal edits: timestamp, user,
  field, previous value, new value, and the engine version active at the
  time — the spec's "every update must retain date, user, previous value,
  new value, and the calculation-engine version" requirement.
- Persist `CalculatedMetrics`/`EnergyPlan` snapshots per log (cached,
  keyed by `log_id` + engine version) instead of always recomputing on
  read, so historical results stay reproducible if the engine changes.
- Add a persisted `Projection` entity (`projection_id, user_id,
  projected_date, estimated_weight, estimated_waist, estimated_neck,
  source_model, base_regression`) so a saved forecast run can be
  inspected later without recomputing, with its regression base recorded.

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

### Phase 1.6 — Testing & native-client groundwork

- Weighted or non-linear projection models beyond OLS.
- Playwright JS unit tests for `views.js`/`api.js`.
- Native Android client using the `remote/RemoteFacade` seam directly
  (no WebView) — an alternative to Phase 2 below for a fully-native UI.

## Android app

Phase 2 (not yet built): package the Phase-1 server + client into an
Android app via **Chaquopy**, launching Flask on a background thread bound
to `127.0.0.1`, with SQLite in the app's private storage
(`JUSTFITTING_DB_PATH`), and a full-screen **WebView** pointed at the local
server once `GET /api/health` returns 200. Phase 1 is already shaped for
this: host/port/DB path are env-configurable, the dev path has no
gunicorn dependency, and `JUSTFITTING_SERVE_CLIENT=true` makes the server
serve the client from the same process. See `docs/composition_spec.md`
and the project's original scaffolding brief for the full roadmap.

## The Team

Danel Arias — University of Deusto, Bilbao.
