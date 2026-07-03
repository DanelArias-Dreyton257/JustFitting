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
| `update.sh` | `conda env update --prune`; apply pending DB migrations. |
| `reset_db.sh [path]` | Delete the SQLite file (confirms unless `FORCE=1`). |
| `seed_demo_data.sh` | Register `admin`/`adminadmin` and seed the Danel reference series. No-op if already seeded. |
| `uninstall.sh [path]` | Remove the conda env and optionally the DB. |
| `build_static_site.py [api_base_url]` | Build the client into `dist/` for a static host or the Android app (see **Android app** below). |

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

## Roadmap: body-composition module capabilities

The consolidated technical spec (`docs/JustFitting_Documento_Final.pdf`,
v2.0) defines the product capabilities this roadmap tracks; full detail,
status per item, and the recommended data model are in
`docs/product_capabilities_spec.md`. Phases are grouped in roughly the
order that unlocked the most value first — all of Phase 1's sub-phases are
done.

A second source document, `docs/JustFitting_Oleada2_Sergio.pdf` (v1.0),
specifies an entirely new bulk/volume module (eight capabilities, F1–F8)
on top of the same core engine; see Phase 3 below, and the "Oleada 2"
sections of `docs/composition_spec.md` (formulas) and
`docs/product_capabilities_spec.md` (capabilities, data model,
validations) for the full spec. A **third** source document,
`docs/JustFitting_TEF_Macronutrientes.pdf` (v1.0), adds a ninth
capability (F9) on top of that module: real TEF computed from logged
carb/fat/protein grams instead of a flat 10% guess — see Phase 3.4.

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
  `GET /api/users/me/report`.
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

### Phase 3 — Oleada 2: bulk/volume engine foundation (planned)

Source: `docs/JustFitting_Oleada2_Sergio.pdf` (F1, F4, F8). Lands the
per-account configuration and BMR model choice everything else in Oleada 2
builds on, without touching any existing (cut-mode) computed values:

- Goal engine grows a `direction = cut | bulk` label derived from
  `weekly_rate`'s sign; a bulk goal validates against the recommended
  `[0.25%, 0.5%]` weekly-rate range and warns (not blocks) outside it.
- A second BMR model, Mifflin–St Jeor, selectable per request/account
  alongside the existing Cunningham model (`bmr_model`).
- `EngineSettings` grows Oleada 2's calibration constants (fat offset,
  FFMI coefficient, lean-tissue kcal/kg, ideal fat ratio), historized like
  every other per-account constant — defaulting to values that reproduce
  today's numbers exactly, never Sergio's own calibration. The weighted
  body-fat formula's RFM/Navy/Deurenberg weights (today a fixed,
  shared-by-everyone `constants.py` triple) become overridable the same
  way, since the offset alone already establishes that this formula needs
  per-account correction — the weights must still sum to 1.
- Bulk mode reuses the existing deficit/target-calorie formula chain
  unmodified — `Pi_i` already goes negative (a surplus) when the weekly
  rate is positive. `docs/composition_spec.md`'s "Formula reconciliation"
  works out why TEF should stay a divisor (not the multiplier the source
  spreadsheet uses) for both directions, so the only actual formula
  addition across all of Oleada 2 is the cardio/EAT term from Phase 3.1
  below, default `0`.

### Phase 3.1 — Oleada 2: cardio input & gain-quality tracking (planned)

Source: `docs/JustFitting_Oleada2_Sergio.pdf` (F2, F3). The central new
capability of the module — "is this bulk clean?":

- A weekly `cardio_kcal` (EAT) field, folded into TDEE for bulk-mode
  accounts.
- A gain-quality panel: weekly and cumulative lean/fat split of the
  week-over-week weight change, with a 25/75 ideal-ratio indicator.

### Phase 3.2 — Oleada 2: energy reconciliation & increment analytics (planned)

Source: `docs/JustFitting_Oleada2_Sergio.pdf` (F5, F7). Closes the loop
between the energy model and what's actually being measured:

- An energy-reconciliation check comparing the surplus implied by intake
  against the surplus implied by next week's measured tissue change, with
  its error (and a rolling mean) surfaced to the user.
- Real-increment analytics: a running mean of the actual weekly increment
  and its normalized deviation from the goal rate.
- Two new alerts extending Phase 1.3's engine: a high fat-ratio week
  ("dirty bulk") and a reconciliation error above threshold
  ("recalibrate").

### Phase 3.3 — Oleada 2: daily and weekly logs coexist (planned)

Source: `docs/JustFitting_Oleada2_Sergio.pdf` (F6), generalized beyond
what the source doc specifies. The natural foundation for the Phase 2.1
"automatic steps import" idea:

- A log row gets a `granularity = daily | weekly` tag (same pattern as
  the existing `source = real | projected` tag) instead of a separate
  daily-entry table that only exists to feed a forced weekly rollup.
  Every week can be logged either way, and even mix over an account's
  history.
- Each **view** resamples whatever's actually stored, in both directions:
  a weekly view of a daily-logged week takes the median weight / mean
  steps+cardio across its days (more robust to daily water/sodium swings
  than a single weigh-in); a daily view of a weekly-logged week
  copy-pastes that log's values across every day since the previous one
  — the same "hold the last known value" idea the projection module
  already uses going forward (`activity_model="constant"`), just applied
  backward across days a single log already covers.
- An account that only ever logs weekly sees no change in behavior.

### Phase 3.4 — Oleada 2: TEF by macronutrients (planned)

Source: `docs/JustFitting_TEF_Macronutrientes.pdf` (F9). The single
biggest precision upgrade in Oleada 2's energy model — comes last in the
sequence because it needs Phase 3.3's daily granularity to have somewhere
to read macros from, not because it's minor:

- Daily carb/fat/protein grams (on a daily-granularity log row — no new
  table, just three more optional fields on the same row Phase 3.3
  introduced) produce a directly-computed daily and weekly TEF in kcal,
  replacing the flat 10% guess: protein costs far more to digest than
  carbs or fat, so two accounts eating the same calories with different
  macro splits get genuinely different, not identical, energy estimates
  — materially relevant for a high-protein bulk.
- `tef_mode = flat | macros`, account setting + optional per-request
  override; a week with no macros logged falls back to the flat estimate
  automatically, regardless of the account's preferred mode — this
  feature is additive, never blocking.
- The TEF-per-gram coefficients (protein highest, fat lowest) are
  literature averages, so they're per-account overridable like every
  other engine constant, alongside a new `GET /api/metrics/tef` view
  breaking a week's TEF down by macro.

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
