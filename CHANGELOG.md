# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- **Chaquopy source set bundled stray repo-root build artifacts into the
  Android APK.** Discovered rebuilding the APK for the v5.0.0 release: a
  previously-built `JustFitting-debug.apk` sitting at the repo root (a
  completely normal thing to have between builds) got swept into the
  Chaquopy Python source set as if it were source, bloating
  `assets/chaquopy/app.imy` from ~0.3MB to ~460MB and the final APK to
  ~480MB (vs. the documented ~40.8MB baseline) — the exclude-only
  pattern list (`android/app/build.gradle`) covered directories but no
  repo-root file types. Added `*.apk`/`*.aab`/`justfitting.db`/
  `justfitting.db-journal` to the exclude list; a clean rebuild
  (`gradlew clean`, needed since Gradle's incremental APK packager had
  patched the bloated file in place rather than rewriting it) now
  reproduces the correct ~41MB size, confirmed by inspecting the built
  APK's own zip contents and a real install/launch on a connected
  device. Not part of the CI/release pipeline (the Android APK is only
  ever built manually via `npm run android:apk`), so no version bump.

## [5.0.0] - 2026-07-10

### Added

Phase 10 (README), GAME CHANGER (2) and GAME CHANGER (3) from
`things-to-improve.txt`'s "Big Remaining Features" — a persistence-layer
foundation paired with the Dashboard's biggest remaining gap:

- **Versioned DB migration protocol** (Phase 10.1). A real migration
  runner returns, justified now by real on-device data (Phase 6): a new
  `server/src/data/db/migrations/` package (`m0001_baseline.py`,
  `m0002_body_measurements_catchup.py`, `m0003_activity_goals.py`), each
  a numbered `upgrade(conn)`, applied in order inside one transaction via
  SQLite's own `PRAGMA user_version` — a failure rolls the whole batch
  back, never leaving a half-migrated file. `m0002` is the protocol's
  first real user: it backfills any surviving `body_logs.waist_cm`/
  `neck_cm` values (still physically present on any device that installed
  Phase 9 before this protocol existed) into `body_measurements`, then
  drops the columns via the standard create-copy-drop-rename sequence,
  carefully avoiding SQLite's rename-following behavior so
  `metrics_snapshots`' foreign key survives and `AUTOINCREMENT` doesn't
  collide with the copied rows. From this phase on, a schema change is a
  new migration module, not a `DB.SCHEMA` edit — established immediately
  by `m0003`'s brand-new `activity_goals` table (below), routed through
  the protocol even though it's purely additive. `scripts/reset_db.sh`/
  `update.sh` and `DB.py`'s own docstring are rewritten for the new
  convention.
- **Today dashboard section** (Phase 10.2). A new "Today" stat-row leads
  the Dashboard, above Weight & Body Composition: steps done, kcals
  eaten, kcal-to-target, and a combined TEF/NEAT/EAT-today block, all
  computed on the fly by a new pure module
  (`services/composition/TodayEstimate.py`) against today's own
  (typically still-partial) log row, holding the most recently *computed*
  week's weight/BMR/target-calories static rather than waiting for a full
  week to close — the same "hold the last known value" idea Phase 9.1
  already established for perimeters, generalized to lean mass/BMR. A new
  `GET /api/metrics/today` route serves it; a new
  `GET /api/logs/by-date/<date>` route is the read-side counterpart of
  Phase 7.4's existing upsert-by-date route. An "Incomplete/current" state
  is inferred (never stored) from whether today's row is `is_computable`
  yet.
- **Daily activity goals** (Phase 10.2, extending the above). A new
  daily steps/cardio-kcal goal, independent of the main body-fat goal in
  the data model (its own `activity_goals` table, historized the same
  create-new/deactivate-old pattern, a parallel `ActivityGoalManager`,
  `GET`/`PUT`/history `/api/users/me/activity-goal` routes) but placed on
  the Plan tab in the UI — a new "Daily activity goal" section under the
  body-fat goal's own history table, rather than a new nav destination or
  Settings. Unset by default (no onboarding step forces it); once set, the
  Today section gains "N left of goal" subtitles on the Steps/Cardio tiles.
- **Health Connect sync now feeds the Today section** (Phase 10.2). Phase
  7.3's "not today" rule is relaxed — `HealthSyncPlugin.java`'s sync
  window now includes today as its last, necessarily partial day, upserted
  through the same by-date route every other synced day already uses; a
  day's true final total still arrives automatically once a later sync
  re-reads it after it's no longer "today." No client-side changes needed
  — "Sync now" already upserts whatever dates it's given.

New coverage: `DB_test.py`'s new `MigrationRunnerTest` (fresh-DB
convergence, the catch-up migration's backfill/foreign-key/AUTOINCREMENT
safety, atomic rollback on a failed batch — plus manual verification
against this repo's own real, already-populated local dev database);
`TodayEstimate_test.py` and `ActivityGoalManager_test.py` (new files);
`Api_test.py` extended for every new route; a new Dashboard Playwright
case exercising a partial today-log plus an activity goal through the
real UI end-to-end. 403 server tests, 67 client tests green.

## [4.0.0] - 2026-07-10

### Added

Phase 9 (README), GAME CHANGER (1) from `things-to-improve.txt`'s "Big
Remaining Features" plus Small Feature 5 — the largest data-model change
since Phase 3.3's daily/weekly coexistence: **body composition logging
separation**. Perimeters (waist, neck, and nine more record-only
measurements) stop being a value required on the same row as
weight/intake/steps and become their own sporadically-logged record, held
"static" from one measurement to the next for every computation in
between.

- **`body_measurements` table and the "static until next update"
  resolution layer** (Phase 9.1). A new table (`measurement_id, user_id,
  date, waist_cm, neck_cm, created_at`, `UNIQUE(user_id, date)`) replaces
  `body_logs.waist_cm`/`neck_cm`, which are dropped entirely. A new
  resolution step (`BodyMeasurementManager.get_effective`) supplies
  `waist_cm`/`neck_cm` from the most recent measurement on or before a
  given date, called by every engine-input builder
  (`MetricsSeriesService`, `plan_routes.py`, `projection_routes.py`) ahead
  of the completeness check — a week with weight/intake/steps but no
  measurement yet stays not-computable, same "not enough data" outcome as
  before, just gated on a different table. No `ENGINE_VERSION` bump: every
  formula and value is byte-for-byte identical for a given
  `(weight, waist, neck, intake, steps)` tuple. `GET /api/users/me/export`
  gains a `body_measurements` array; `POST /api/users/me/import` accepts
  it, and — for backward compatibility with a pre-Phase-9 export file —
  still detects inline `waist_cm`/`neck_cm` on a `logs[]` entry and
  synthesizes a `body_measurements` row from it rather than discarding
  them. `Projection.py`'s waist/neck trend-fit source moves from
  `body_logs` to `body_measurements`' own sparser, irregularly-dated
  history, falling back to holding the last resolved value constant when
  fewer than two measurements exist to fit a trend against.
- **Separate "Body" tab; Log wizard drops perimeters** (Phase 9.2). A new
  nav destination, "Body," backed by a new `GET`/`POST /api/body-measurements`
  + `PUT`/`DELETE /api/body-measurements/<id>` route set — a simple
  date-picker plus form and history table, no wizard needed. The Log
  wizard drops from 4 steps to 3 (Date & weight → Energy → Review);
  `weight_kg` now sits alongside intake/steps/cardio/macros on the same
  cadence. The Dashboard's Waist/neck chart is repointed from the old
  `GET /api/logs` + `GET /api/metrics/series` merge to
  `GET /api/body-measurements` directly, rendered as a new **held/step
  line** (`charts.js`'s `drawStepLineChart`) instead of the diagonal
  interpolation every other chart uses, visually communicating "this
  value didn't change, we just haven't measured again yet." The Dashboard
  forecast toggle's waist/neck overlay is unaffected in shape.
- **Expanded body measurements** (Phase 9.3, Small Feature 5). Nine more
  nullable, record-only columns on `body_measurements` — `shoulder_cm,
  chest_cm, hips_cm, biceps_r_cm, biceps_l_cm, thigh_r_cm, thigh_l_cm,
  calf_r_cm, calf_l_cm` — never read by `CompositionEngine`. The Body
  view's form gains a Quick (waist/neck only) / Full (all eleven) toggle;
  a blank field on a Full save leaves that field's most recent value
  untouched rather than resetting it to blank, and the history table
  resolves a blank cell the same "most recent non-null value as of this
  date" way waist/neck already do. `BodyMeasurementDTO` and the JSON
  export/import contract extend to the full column set; deliberately not
  extended to CSV (no case for a second CSV pipeline over a record-only,
  low-volume field set the JSON path already covers).

New coverage: a new `BodyMeasurementManager_test.py`; `DB_test.py`,
`LogManager_test.py`, `LogResampler_test.py` (a new
`ResolveMeasurementsTest`), `MetricsCache_test.py`,
`MetricsSeriesService_test.py`, and `DemoSeeder_test.py` all updated for
the schema split; `Api_test.py` updated across ~30 tests (`waist_cm`/
`neck_cm` removed from every `/api/logs` payload, `POST
/api/body-measurements` seeding added wherever a test needs a computable
week); `Log_test.py`/`Dashboard_test.py`/`Plan_test.py`/`Views_test.py`
(Playwright) updated for the 3-step wizard and the new Body view, with
the retired Phase 5.4 perimeter-prefill test removed. Also fixed a real
bug caught along the way: navigating to the new Body view fired an
unawaited fetch-and-reset that could clobber a fast-typing user's
in-progress entry (the same navigate()-races-an-unawaited-refresh shape
already fixed for the Log/Account/Settings views in earlier releases).
376 server tests, 66 client tests green.

### Fixed

- **A real, pre-existing `navigate()`/`refreshLogs()` race**, caught by
  CI (two Playwright timeouts that never reproduced locally): `refreshLogs()`
  ran `goToLogStep(1)` *after* its `await api.listLogs()`, and
  `navigate("log")` has always called it unawaited -- a fetch that
  resolved late (slow network/CI) could silently reset an in-progress
  wizard back to step 1, hiding `#log-save` right as something tried to
  click it. Predates Phase 9 entirely; narrowed to actually land by the
  Log wizard shrinking to 3 steps and the new Body-tab round trip adding
  more real network time before reaching it. Fixed the same way as the
  Account/Settings/Body races before it: the resets don't depend on the
  fetched data, so they're hoisted into `refreshLogs()`'s synchronous
  head instead of its async tail. Reproduced locally by throttling the
  API before the fix, confirmed gone after it.

## [3.1.0] - 2026-07-10

### Added

Phase 8 (README), the first of the round-3 beta-testing phases --
`things-to-improve.txt`'s "Good improvements" section, two goal-plan
correctness fixes:

- **Retroactively editable goal start date** (Phase 8.1). A new goal's
  `start_date` was always stamped "today," which since Phase 5.3 scopes
  every computed series/chart/alert/projection to "this goal's own
  period" once an account has ever changed goals -- a user already
  mid-cut or mid-bulk before adopting JustFitting had no way to tell the
  app their current goal actually started earlier, silently excluding
  real, already-logged history from its own trajectory/adherence/forecast.
  A new `GoalPlanManager.update_start_date`, exposed as `PUT
  /api/users/me/goals/active/start-date`, corrects the *active* goal's
  `start_date` in place (not a new historized row), bounded to on-or-before
  today and strictly after any previous goal's own start date, audited
  and cache-invalidated like every other goal mutation. The Plan tab's
  "Current plan" section gains an "Edit start date" control, its date
  input's `min`/`max` mirroring those same bounds.
- **Reject incoherent target-BF/weekly-rate combinations** (Phase 8.2). A
  candidate goal was never compared against the account's actual current
  body fat -- e.g. `target_bf=0.15` (a "lose fat" target) with a positive
  `weekly_rate` (a bulk rate) was accepted silently. A new
  `GoalPlanManager.check_goal_coherence` runs in both
  `GoalPlanManager.create_goal_plan` (before committing a real goal
  change) and `GET /api/plan/preview` (before commit, not after): a
  fat-loss target requires a non-positive rate, a fat-gain target
  requires a non-negative one, and a target within half a percentage
  point of the current figure allows any rate (maintenance/recomp). The
  check is skipped entirely for an account with no computable log yet
  (e.g. a brand-new default goal). Sign coherence only -- magnitude
  bounds for a bulk rate remain `bulk_rate_out_of_range`'s job (Phase 3).

New coverage: `GoalPlanManager_test.py` gained cases for the coherence
function, `create_goal_plan`'s new `current_bf` parameter, and
`update_start_date`'s bounds/audit/cache-invalidation; `Api_test.py`
gained cases for the new start-date route and for both `PUT
/api/users/me` and `GET /api/plan/preview` rejecting/allowing a goal
against a seeded account's real computed body fat; a new
`client/test/browser/Plan_test.py` (Playwright) covers the start-date
control's default value and native `max`-date validation, a persisted
edit, and the preview form's inline error for an incoherent goal. 362
server tests, 65 client tests green.

## [3.0.2] - 2026-07-09

### Fixed

Three bugs reported against the Health Connect sync (README's Phase
7.3-7.5), `things-to-improve.txt`'s "FOUND BUGS" section:

- **Sync silently capped at 30 days regardless of the requested window.**
  Health Connect clamps every read to the last 30 days unless the app also
  holds the `android.permission.health.READ_HEALTH_DATA_HISTORY`
  permission -- undocumented in this project until now, since the original
  Phase 7.3 implementation only ever requested `READ_STEPS`/
  `READ_NUTRITION`. `AndroidManifest.xml` and `HealthConnectBridge.kt` (the
  `HISTORY_PERMISSION` constant, included in `allPermissions()` so the
  "Connect" button's system dialog now asks for it too) gained the new
  permission. `HealthSyncPlugin.readRecentReadings`'s own gate now checks
  a narrower `HealthConnectBridge.requiredPermissions()` (Steps + Nutrition
  only) rather than `allPermissions()`, so a user who declines the extra
  history permission still gets ordinary (30-day-clamped) sync instead of
  being locked out entirely.
- **A weekly log and same-week daily syncs never actually combined.**
  `LogResampler.resample_to_weekly` only ever grouped daily-tagged rows
  with each other; a manually-entered weekly log (typically perimeters
  only) sharing its ISO week with Health Connect's daily-synced steps/
  nutrition rows was left completely untouched, passed straight through
  next to a *separate*, differently-incomplete representative row for that
  same week -- so neither row alone had everything the engine needs, even
  though the week's data was genuinely complete once combined. Reported
  as: a daily week that only ran Monday-Wednesday (today being Thursday),
  plus a weekly log entered for the rest of that week's body-comp data,
  produced "cannot compute a row missing required fields: intake_kcal,
  steps" when previewing a new Goal Plan. `resample_to_weekly` now
  completes a single weekly row sharing its ISO week with a daily group
  in place -- filling only whichever of its own fields are still missing
  from the daily group's existing mean/median aggregate, never overwriting
  a field the weekly row already has -- rather than leaving two
  incomplete rows for the same week. Two or more weekly rows sharing an
  ISO week are left untouched, same as before (which of them would
  "own" the merge is ambiguous). Separately, `GET /api/plan/preview` and
  `GET`/`POST /api/projection` (`plan_routes.py`, `projection_routes.py`)
  built their engine input from the raw, unresampled log list ordered by
  date -- unlike `MetricsSeriesService.compute_series_for_user`, which
  already resamples and filters to computable rows -- so even a
  genuinely-complete-once-resampled week could still crash if it happened
  to be the most recent *raw* row. Both routes now build their engine
  input from the same resample-then-filter-computable pipeline, returning
  a plain 404 ("no computable logs yet") instead of a raw compute error
  when nothing computable exists yet.
- **Macros synced from Health Connect stored with excessive decimal
  precision.** `NutritionRecord`'s `Energy`/`Mass` aggregates are
  floating-point sums (e.g. `carbs_g: 210.00000000000003`), a
  sum-of-floats artifact rather than meaningful extra precision.
  `healthSync.js`'s `syncRecentReadings` now rounds every numeric field
  (steps, intake_kcal, carbs_g, fat_g, protein_g) to 1 decimal place at
  the boundary where a native reading enters the JS layer -- before it's
  ever stored via `PUT /api/logs/by-date`, not just before display --
  leaving a field the reading never had (no key at all) untouched rather
  than introducing one.

New coverage (README's Phase 7.6): `LogResampler_test.py` gained three
cases for the weekly/daily same-ISO-week merge (completes in place,
never overwrites the weekly row's own fields, two weekly rows in the
same week stay untouched); `Api_test.py` gained an end-to-end regression
reproducing the exact reported scenario (daily syncs Mon-Wed, a Thursday
weekly log, `GET /api/plan/preview` now 200s and `GET /api/metrics/latest`
reflects the combined steps/intake); a new
`client/test/browser/HealthSync_test.py` (Playwright, mocking the native
plugin) covers the rounding behavior. 339 server tests, 61 client tests
green; `gradlew :app:compileDebugJavaWithJavac :app:compileDebugKotlin`
confirms the Android side builds. The 30-day-cap fix still needs a real
device to confirm -- no emulator/unit test can exercise Health Connect's
own read-clamping behavior.

## [3.0.1] - 2026-07-09

### Fixed

- Fixed a real, pre-existing race surfaced by v3.0.0's own release
  workflow CI gate failing (the tag never actually deployed): `navigate()`
  called the async `refreshSettings()` without awaiting it, and
  `refreshSettings()` only set `#settings-show-projected-logs`'s checked
  state (from `getShowProjectedLogs()`, a synchronous `localStorage`
  read with no legitimate reason to be sequenced after a network fetch)
  after first awaiting two unrelated API calls. A test (or a real user)
  interacting with that checkbox right after navigating to Settings could
  race the JS-driven assignment and have its own click silently
  overwritten -- the same `navigate()`-races-an-unawaited-refresh shape
  already fixed twice before, in the Log view and the Account view (see
  v2.0.1's entry below). Fixed the same way: the purely local assignment
  is now set synchronously in `navigate()`'s own dispatch, before
  `refreshSettings()` (which still needs its network calls for the rest
  of the view) even starts, closing the race window entirely rather than
  just narrowing it. Verified with 3 consecutive full local client-suite
  runs, all green.

## [3.0.0] - 2026-07-09

### Added

- Phase 7.1 (data portability, see README): hardened `POST
  /api/users/me/import`, which already existed but had three real gaps --
  it silently dropped `granularity`/macro fields on re-import, crashed
  with an unhandled `sqlite3.IntegrityError` on a duplicate date instead
  of skipping that row, and trusted the imported file's own `source`
  field, letting an import forge a `"projected"` row. All three are
  fixed; the route now also reports which rows were skipped and why
  (`skipped: [{row, reason}]`) instead of swallowing failures silently,
  and the client renders an "Imported N, skipped M (reasons)" summary
  instead of a blind refresh. New `LogManager.get_by_date`.
- Phase 7.2: CSV import over the same hardened pipeline as JSON --
  `client/src/webapp/static/js/csvImport.js`, a small hand-rolled
  RFC-4180-ish parser (no new JS dependency), turns a CSV file into the
  exact `{logs: [...]}` shape the JSON path already sends, so it gets
  Phase 7.1's validation, dedup, and per-row reporting for free. Every
  field is type-coerced client-side (real numbers, real booleans) rather
  than left as raw strings, since Python's `bool("false")` is `True`. The
  Import control now accepts `.json`/`.csv`; a downloadable CSV template
  is linked next to it.
- Phase 7.3 (Android app only): a Health Connect bridge reading Steps
  (Mi Fitness) and Nutrition (Samsung Health) data those apps already
  sync into Android Health Connect on-device -- confirmed both are
  reachable through Health Connect alone, no proprietary Xiaomi/Samsung
  API needed. Read-only, manual "Sync now" trigger only, no background
  job. `androidx.health.connect:connect-client` needs minSdk 26
  (`android/variables.gradle` bumped `24 -> 26`) and is pinned to
  `1.1.0-alpha08`, not the current stable `1.1.0`, which needs compileSdk
  36 + a much bigger AGP bump than this phase's scope justified. Its API
  is entirely Kotlin-suspend-based with no supported Java interop path,
  so `HealthConnectBridge.kt` -- the one Kotlin file in this app -- wraps
  every call in `runBlocking` and exposes plain synchronous methods;
  everything else, including the new `HealthSyncPlugin.java` Capacitor
  plugin (`isAvailable`/`hasPermissions`/`requestPermissions`/
  `readRecentReadings`) and `MainActivity.java`, stays plain Java.
  `AndroidManifest.xml` gained the two read-only health permissions, a
  `<queries>` entry for Health Connect's own package, and the
  permissions-rationale intent-filters Health Connect requires. New
  `client/src/webapp/static/js/healthSync.js` wraps the plugin with a
  graceful fallback for the web build and any non-Android device.
- Phase 7.4: partial logs and independent-source merging. Steps
  (Mi Fitness), nutrition (Samsung Health), and body measurements are now
  genuinely independent -- any one can arrive first, any can be missing
  or fail, and completing a day is just filling in whatever's still
  missing on the same row, in any order. `body_logs`'s `weight_kg`/
  `waist_cm`/`neck_cm`/`intake_kcal`/`steps` become individually
  nullable; `validate_log_input` now allows `None` (if present, still
  must be positive); `CompositionEngine.compute_row` gains a
  completeness guard (`require_complete_log_input`, a clear error naming
  missing fields, defense-in-depth only -- `ENGINE_VERSION` does not
  bump); `LogResampler`'s daily-group median/mean generalizes to skip
  `None`s, and a new `is_computable` check excludes a still-incomplete
  resampled week from the computed series, same as an unlogged week.
  New `LogManager.upsert_fields`/`PUT /api/logs/by-date/<date>`: merges
  given fields into an existing row for a date, or creates a new partial
  row scoped to just those fields -- the order-/source-independent
  primitive Phase 7.5's sync uses. `POST /api/logs` and the Phase 7.1
  import route both relax from requiring all five fields to accepting
  any subset; import keeps its skip-on-duplicate-date default unchanged.
- Phase 7.5: "Sync now" writes synced readings directly as partial logs
  via the new upsert-by-date endpoint, per source, instead of an earlier
  client-side-cache-and-prefill design -- a synced day is a real row the
  moment it's synced. Completing a day is exactly the existing log-edit
  flow. The Account view's Export/Import section is retitled "Data
  import, export & sync" and gains (Android only) a Connect button, a
  "Sync last N days" field (default 7, capped at 90), a Sync now button,
  a per-source connected status line, and a last-synced timestamp.
  Fixed `HealthSyncPlugin.hasPermissions()` (Phase 7.3) to report
  Steps/Nutrition independently instead of one combined boolean, needed
  for the per-source status line. The log table and wizard now render a
  partial row's missing fields as a dash/blank input instead of the
  literal string `"null"`. Export/Import/Connect/Sync now buttons match
  the app's existing blue button styling.

### Fixed

- Phase 7.3/7.5, found via real-device testing (see README's "Verified
  on a real device"): `HealthConnectBridge.readDailyReadings` built its
  query range from `Instant`s, which fails at runtime against
  `aggregateGroupByPeriod` ("Either use TimeRangeFilter with
  LocalDateTime or AggregateGroupByDurationRequest") -- a constraint
  enforced at runtime, not encoded in `TimeRangeFilter`'s type, so no
  amount of compiling or static analysis could have caught it. Fixed by
  building the range from `LocalDate.atStartOfDay()` instead.
- The Account-view health-sync section only appeared after visiting
  Settings first -- `refreshHealthSyncUI()` was wired to `navigate()`'s
  `"settings"` case, but its markup actually lives in the Account view,
  not the engine-constants Settings view. Fixed by moving the call to
  the `"account"` case.

## [2.0.1] - 2026-07-09

### Fixed

- Fixed a real, if narrow-window, bug in the Account view surfaced by a
  CI-only flake (`Account_test.AccountTest.
  test_editing_profile_fields_round_trips_without_touching_the_active_goal`,
  not reproducible locally, failing intermittently -- twice -- on the
  `v2.0.0` release workflow's test gate). `navigate("account")` called
  `refreshAccount()`, which re-fetched `GET /api/users/me` unawaited and
  repopulated the profile form from the response. `state.profile` is
  always already fresh by that point (set once at `boot()`, before any
  navigation is possible), so this re-fetch was redundant -- and racy: if
  it resolved after a user had already started editing the form but
  before submitting, it silently overwrote their in-progress edits with
  the stale pre-edit profile, sometimes causing the submitted PUT to
  carry the old values instead of the new ones. Same root-cause shape as
  the previous Log-view fix (`navigate()` racing an unawaited refresh
  function) -- fixed the same way: `navigate()` now renders the form
  synchronously from already-known `state.profile` instead of kicking off
  an async re-fetch, so there's no longer an in-flight operation to race
  against. The now-fully-redundant `refreshAccount()` function (its only
  caller) was removed.

## [2.0.0] - 2026-07-09

### Added

- Phase 6 (embedded on-device server for Android, see README): first step
  landed -- the Chaquopy Gradle plugin (`com.chaquo.python:gradle:17.0.0`)
  is wired into `android/build.gradle`/`android/app/build.gradle`,
  configured to pip-install this project's actual server dependencies
  (`server/requirements-prod.txt`: Flask, flask-cors, python-dotenv,
  waitress) for an on-device Python 3.12 interpreter. Three
  version-specific issues surfaced and were resolved while wiring this
  up: Chaquopy 17 requires `minSdkVersion >= 24`
  (`android/variables.gradle` bumped `22 -> 24`, dropping Android
  5.1/6.0 support); its build-time interpreter (used to resolve pip
  packages, separate from the on-device runtime) must match the
  on-device Python version exactly, and the desktop `justfitting` conda
  env resolves to Python 3.12.13 (not `environment.yml`'s `>=3.10`
  floor), so the on-device version is pinned to `"3.12"` rather than
  Chaquopy's own 3.10 default -- resolved without hardcoding a
  machine-specific interpreter path, by relying on `conda activate
  justfitting` putting the matching `python` on `PATH`; and Python 3.12
  only ships Chaquopy builds for 64-bit ABIs, so `ndk.abiFilters`
  narrowed from all four ABIs to `arm64-v8a`/`x86_64`. Verified with a
  real `assembleDebug` run: Flask 3.1.3, flask-cors 4.0.2, python-dotenv
  1.2.2, waitress 3.0.2 and their transitive dependencies installed
  cleanly for both ABIs, no C-extension/wheel problems; the debug APK
  grew from the pre-Chaquopy ~4.1 MB baseline to ~40.8 MB with both ABIs
  bundled in one file (a release build should split per-ABI). Not yet
  done: anything that actually starts or talks to the embedded server --
  see README's "Android app -> Embedded on-device server" section for
  the full design and remaining steps.
- Phase 6, continued: the embedded server now actually runs. A new
  `chaquopy.sourceSets` entry (`android/app/build.gradle`) adds the repo
  root as a Python source directory (excluding `server/test/**` and any
  `*_test.py`), so the app imports the literal `server.src.*` package
  from its real location instead of a copy. A new
  on-device entry point, `android/app/src/main/python/local_server.py`,
  starts the same Flask app `server/src/api/app.py` builds, served by
  waitress (matching `server/wsgi.py`'s production path) bound to
  `127.0.0.1:5000`, with `JUSTFITTING_DB_PATH` pointed at the app's
  private storage; idempotent, so Android re-running `onCreate()` (e.g. a
  config change) is a no-op rather than a crash. Its own desktop-runnable
  test, `local_server_test.py` (excluded from the shipped APK), passes
  against a real socket. `MainActivity.java` (plain Java -- the existing
  Capacitor project already is Java, no new bridge language needed) calls
  into it in `onCreate()`, before `super.onCreate()`, so the client's
  first fetch can't race an unbound socket. A new
  `network_security_config.xml`, wired into `AndroidManifest.xml`, scopes
  Android's cleartext-HTTP exception to `127.0.0.1` only, unlike the
  existing dev-only blanket `cleartext: true` used for LAN/emulator
  testing. `package.json` gained `build:web:android-embedded` and
  `android:sync:embedded` targets pointing the client's
  `JUSTFITTING_API_BASE_URL` at the embedded server -- added alongside,
  not replacing, the existing emulator/LAN-pointed `android:sync`/
  `android:apk` scripts, so today's client-only debugging workflow is
  unaffected. Verified: a real `assembleDebug` succeeds with every piece
  wired together, and the full desktop `server/test` suite (310 tests)
  still passes untouched. Not yet done: installing the built APK
  (`JustFitting-debug.apk`) on an actual Android device or emulator --
  no desktop check can confirm the WebView actually loads real data
  through the embedded server.
- Phase 6 complete: verified end-to-end on a real Android device, and one
  real bug found and fixed along the way. The initial
  `chaquopy.sourceSets` config used `include("server/**")` to scope the
  repo-root source directory to just the `server` package; a Gradle
  `SourceDirectorySet`'s include/exclude patterns apply globally across
  *every* srcDir registered on it (matched relative to each srcDir's own
  root), not just the one they were written for, so that include pattern
  also silently filtered `local_server.py` out of this module's own
  default `src/main/python` srcDir -- crashing the app on launch with
  `com.chaquo.python.PyException: ModuleNotFoundError: No module named
  'local_server'`, despite `assembleDebug` succeeding (a filtered-out
  source file isn't a build error). Diagnosed via `adb logcat` against
  the real device and fixed by dropping the `include(...)` allowlist for
  `exclude(...)`-only patterns, which only ever remove matches rather
  than acting as an allowlist against srcDirs they weren't written for.
  After the fix, verified on a real phone (`adb install` + launch, with
  `adb logcat` confirming no crash and a real listening socket on
  `127.0.0.1:5000` answering `GET /api/health`): registering a new
  account, logging a week's data, viewing the real computed Dashboard,
  data surviving a force-close and reopen (the actual "persistence on the
  phone" promise this phase exists for), and full functionality in
  Airplane Mode (confirming the app never reaches Render). Phase 6 is
  done.
- Phase 6 polish, closing out its remaining open items:
  - **Cold-start UX**: `MainActivity.onCreate()` no longer blocks the
    main thread on server startup. It now installs the platform splash
    screen (`androidx.core.splashscreen`, using Capacitor's own
    `AppTheme.NoActionBarLaunch` theme, scaffolded but previously
    unused), starts Chaquopy and `local_server.py` on a background
    thread, and calls `super.onCreate()` immediately so the WebView
    starts loading the bundled shell right away; the splash stays on
    screen (`setKeepOnScreenCondition`) until the server signals ready.
    A second real bug surfaced and was fixed getting here:
    `installSplashScreen()` without a `postSplashScreenTheme` declared
    crashed the app with `IllegalStateException: You need to use a
    Theme.AppCompat theme (or descendant) with this activity`, since
    Capacitor's `BridgeActivity` (an `AppCompatActivity`) checks the
    active theme in its own `onCreate()`, and without that attribute the
    splash-screen library never restores the real AppCompat-descended
    theme. Fixed by adding `postSplashScreenTheme` to
    `AppTheme.NoActionBarLaunch` (`res/values/styles.xml`), pointing at
    the existing `AppTheme.NoActionBar`. `android/app/build.gradle`
    gained an explicit `compileOptions` (Java 8) for the lambdas this
    uses.
  - **Chaquopy licensing**: resolved -- MIT-licensed since v12.0.1 (this
    project uses 17.0.0), free for commercial/closed-source use, no
    royalties, published to Maven Central. No longer an open question.
  - **`android:sync`/`android:apk` now build the embedded target by
    default**, matching what actually ships: `build:web:android` (and
    therefore `android:sync`/`android:apk`) now points at
    `http://127.0.0.1:5000`; the previous emulator/LAN-dev behavior moved
    to explicitly-named `build:web:android-remote-dev`/
    `android:sync:remote-dev` scripts rather than being removed, since
    it's still useful for iterating on client-only changes without
    rebuilding the whole Chaquopy-bundled APK each time.
  - `android/app/build.gradle`'s `versionName`/`versionCode` -- never
    previously bumped past their Phase-2-scaffold defaults through
    v1.2.0/v1.2.1 -- are now `2.0.0`/`2`, tracking this repo's own
    `vX.Y.Z` release tags for the intended v2.0.0 release.
  - Verified on the real device again after all of the above: clean
    launch (screenshot-confirmed the Log view rendering with data from
    the earlier test session intact), server still answering
    `GET /api/health` through a real socket, app version reporting
    `2.0.0`, still fully functional in Airplane Mode.

## [1.2.1] - 2026-07-08

### Fixed

- The Android app's launcher icon was still Capacitor's default placeholder
  (a white background with a generic angular mark) instead of JustFitting's
  own logo. All launcher icon assets --
  `mipmap-{m,h,xh,xxh,xxxh}dpi/ic_launcher{,_round}.png` (legacy icons) and
  `mipmap-{m,h,xh,xxh,xxxh}dpi/ic_launcher_foreground.png` (the adaptive-icon
  foreground layer, Android 8+) -- are regenerated from the same
  `icon-512.png` "JF" mark already used as the web app's favicon/PWA icon,
  and the adaptive icon's background color
  (`values/ic_launcher_background.xml`) changed from the placeholder white
  to the logo's own `#0f1115`, so the installed app icon now matches the
  website/PWA icon exactly.

## [1.2.0] - 2026-07-08

Phase 4.4-4.5 and Phase 5.1-5.10: the day/week log navigator, retiring the
standalone Projection view, and the full second round of beta-testing
feedback (`things-to-improve.txt`) -- goal-free registration, active-goal
-period scoping, wizard perimeter prefill, the "Weight to goal"/Calories
summary fixes, log editing, a profile-only Account view, target-first Goal
tiles, and the unconfigured-goal alert -- plus the self-versioning
service-worker cache and the flaky Log-view navigation race fix. This
release completes both Phase 4 and Phase 5 of the beta-testing UX
refinement work.

### Added

- The Log view's table gained an "Edit" button next to Delete (README's
  Phase 5.7) -- opens the same 4-step wizard already used for creating a
  log, pre-filled with that row's values, with its Save button reading
  "Save changes" and a new "Cancel" affordance. The log's date and
  granularity aren't editable (shown locked); every other field is.
  `PUT /api/logs/<id>` and `LogManager.update_log` already existed
  end-to-end -- this phase is purely the missing client UI.
- A new dismissible alert, `"unconfigured_goal"` (README's Phase 5.10),
  tells a brand-new account that its first goal (15%/22% body fat by sex,
  0% weekly rate -- Phase 5.2's registration default) was auto-assigned
  and points it at the Plan tab -- flows through the existing persisted
  alerts pipeline unchanged, so it shows on the Dashboard even before any
  log exists. Inferred with no schema change: it fires only while the
  active goal is the account's one-and-only-ever goal plan
  (`goal_history_count == 1`) and its `weekly_rate` is still exactly
  `0.0` -- any deliberately chosen goal necessarily has a nonzero rate,
  and committing a goal via the Plan tab always historizes a new goal
  row, so this can never re-trigger once the user has actually visited
  the Plan tab.
- The Dashboard's Calories section gained a fourth tile, "This week's
  intake" (the latest real log's `intake_kcal`, placed before Adherence),
  and a small subtitle line under each tile clarifying what each figure
  actually means (README's Phase 5.6, `things-to-improve.txt`'s second
  beta-testing round, item 6): "Target calories" -> what to eat, "TDEE"
  -> estimated calories burned, "Adherence" -> actual vs target/day (its
  value itself now reads e.g. "-180 kcal" instead of "-180 kcal/day",
  since the subtitle carries that). Purely a labeling/presentation fix
  over already-correct numbers -- no engine or API change.
  `client/src/webapp/static/js/app.js`'s `refreshDashboardSummary()` now
  also fetches `GET /api/logs` to source the new tile's value.

### Changed

- Computed series/charts/alerts/adherence/projections/reports now scope to
  the active goal's own period once an account has actually changed its
  goal (README's Phase 5.3) -- previously, changing goals (e.g. finishing
  a cut, starting a bulk) silently recomputed every historical week's
  target/trajectory/deficit as if the new goal had applied the whole
  time, and fed pre-change data into the forecast's trend regression. A
  new `GoalPlanManager.active_period_start(user_id)` returns `None` (no
  scoping) for an account that's never changed its goal -- not just the
  active goal's `start_date` unconditionally, since every account's very
  first goal is created "today" at registration, and a plain filter would
  otherwise exclude any log dated before signup for every single-goal
  account. `GET /api/logs`/`/export` (raw history) are unaffected --
  only the derived series is scoped.
- Both demo accounts (`admin_cut`/`admin_bulk`, `services/DemoSeeder.py`)
  now seed with a two-goal history instead of one, so they exercise the
  Phase 5.3 scoping above out of the box: `admin_cut` registers at 17%
  body fat/-0.5% weekly, then switches to 15%/-1% 8 weeks before its last
  reference log; `admin_bulk` registers at 20%/+2%, then switches to
  18%/+0.05%. The "Demo_cut worked example" in this README is updated to
  match `admin_cut`'s actual active goal (`Wobj`/`DailyDeficit`/
  `TargetCal`/`Weeks` all depend on `weekly_rate`, unlike the rest of the
  figures there).
- Registration no longer asks for a goal, and the Account view is
  profile-only (README's Phase 5.2/5.8). `POST /api/users` drops its
  `target_bf`/`weekly_rate` requirement -- an omitted goal resolves to a
  sane per-sex default (15% body fat male / 22% female, 0% weekly rate =
  "no change yet"), still creating an active goal plan under the hood
  (explicitly passing `target_bf`/`weekly_rate` keeps working exactly as
  before). The register form and the Account view's profile-form both
  drop their Target body fat/Weekly rate fields entirely -- Account's
  heading changes from "Goal & profile" to "Profile" -- so the Plan tab's
  preview -> commit flow is now the **only** place a goal ever changes,
  for both a brand-new account and an existing one editing later.
- The Dashboard's Goal section now leads with the **target** figure
  instead of the current one, with an arrowed (▲/▼/–) "to goal" subtitle
  showing the remaining distance -- the same `.delta` visual language the
  Weight & Body Composition section above it already uses for
  week-over-week change (README's Phase 5.9, a follow-up refinement past
  `things-to-improve.txt`'s original eight items). "Body fat vs target" ->
  "Target body fat" (value is now `target_bf`, e.g. "15.0%", subtitle "▼
  -4.8% to goal"); "Weight to goal" -> "Target weight (keep lean)" (value
  is now `final_weight_kg`, subtitle "▼ -5.1 kg to goal" --
  the same Phase 5.5 formula, sign-flipped into a direction-of-travel
  delta). A new `formatGoalDelta()` helper (`views.js`) renders this
  alongside the existing `formatDelta()` used for weekly deltas.
- The service worker's cache name (`client/src/webapp/static/sw.js`) is
  now computed at runtime from a SHA-256 hash of the app shell files'
  own bytes instead of a manually-bumped `CACHE_NAME` literal (README's
  Phase 5.1, `things-to-improve.txt`'s second beta-testing round, item
  1). `install` fetches, hashes, and populates the freshly-named cache in
  one pass; `activate` re-derives the current name and purges every other
  `justfitting-shell-*` cache; the `fetch` handler's write-back looks up
  the live cache name via `caches.keys()`. Editing any shell file now
  changes its cache automatically -- this is the last release whose
  changelog will ever say "`CACHE_NAME` bumped".
- The log wizard's Steps field now defaults to `0` and is no longer
  `required`, matching the existing Cardio field's convention, instead of
  blocking submission until a value is typed.
- The log wizard now pre-fills Waist/Neck from the account's most recent
  real log at every "fresh wizard" reset point (entering the Log view,
  switching day/week view) instead of always opening blank (README's
  Phase 5.4, `things-to-improve.txt`'s second beta-testing round, item
  4). Weight and intake/steps/cardio/macros are left blank, since those
  are meant to be re-measured/re-entered every time, not carried forward.
  A brand-new account's first-ever wizard still opens blank.
- Retired the standalone Projection view/nav tab (README's Phase 4.5, the
  fifth and final item from `things-to-improve.txt`'s first round of
  beta-testing feedback, completing Phase 4). The Dashboard's existing
  forecast toggle (Phase 4.3) is unchanged; the Log view now shows
  forecasted future dates as a row injected directly into its log table
  -- same columns a real log uses, tagged with a "projected" badge and a
  "weekly" granularity badge (the forecast is always weekly-cadence), no
  Delete button, weight/waist/neck rounded to 1 decimal, and fields the
  forecast never observed (intake/steps/cardio/macros) shown as "--" --
  rather than a separate widget. It's gated by a new "Show projected
  values on future dates" checkbox in Settings, stored in `localStorage`
  (`session.js`'s `getShowProjectedLogs()`/`setShowProjectedLogs()`,
  defaulting on for a first-time user) rather than as a server-persisted
  account setting, since it's a display preference, not an engine input
  -- it persists across sessions on the same browser once explicitly
  toggled, unlike the Dashboard's own toggle which resets every login.
  `app.js`'s Phase 4.3 forecast-fetch/cache logic is
  generalized into one `fetchProjectionWeeks(weeks)` helper shared by
  both the Dashboard toggle and the Log view's row injection. Purely
  client-only, like every other Phase 4 sub-phase -- no server/DB
  changes, no `ENGINE_VERSION` bump. `sw.js`'s `CACHE_NAME` bumped
  `-v14` -> `-v15`. New Playwright coverage in
  `client/test/browser/Log_test.py` (turning the Settings preference on
  and navigating past the last logged week injects a tagged, undeletable
  projected row; turning it off removes it; navigating to a day with a
  real log shows only that real, deletable row even with the preference
  on); `Client_test.py`'s markup assertion on the removed standalone
  view's `#projection-activity` control is replaced with an assertion
  that no `data-view="projection"` nav link or `#view-projection` section
  remain, and that `#settings-show-projected-logs` exists.

- Redesigned the Log view's log capture around a day/week navigator
  (README's Phase 4.4, the fourth item from `things-to-improve.txt`'s
  first round of beta-testing feedback): a `‹`/`›` arrow pair, a Day/Week
  toggle, and a date-picker sit above the existing wizard, defaulting to
  today's day view. The wizard's date is now derived from the
  navigator's selected day (a "Logging for **`<day>`**" label plus a
  hidden field) instead of a freely-editable date input, and the table
  underneath only ever shows that day's (or that ISO Monday-Sunday
  week's) logs, with a "No logs for this day/week yet." placeholder when
  empty -- replacing the previous unbounded "every log ever" table.
  Purely client-only: `GET /api/logs` already returns every log for the
  account in one call, so the navigator is a client-side filter over
  data already fetched, not a new endpoint -- no migration, no
  `ENGINE_VERSION` bump. The granularity selector's default follows the
  active view mode (daily in day view, weekly in week view) at each
  fresh-wizard point (opening the Log view, switching day/week, and
  after a save), without overriding a manual mid-entry choice.
  `sw.js`'s `CACHE_NAME` bumped `-v13` -> `-v14`. New Playwright coverage
  in `client/test/browser/Log_test.py` (default today/day-view empty
  state, a saved log landing in the selected day, arrow navigation, and
  week view grouping multiple same-ISO-week logs that day view keeps
  separate); `Dashboard_test.py`'s own log-creation helper updated to
  drive the new date-picker instead of the now-hidden date input.

### Fixed

- The Dashboard's "Weight to goal" tile (README's Phase 5.5,
  `things-to-improve.txt`'s second beta-testing round, item 5) showed
  `weight_to_shed_kg` -- this week's incremental target change, which for
  a steady weekly rate is always roughly the same figure (reported as "a
  flat 0.5kg") regardless of actual proximity to the goal -- instead of
  the total remaining distance. It now reads `(fat_mass_kg + lean_mass_kg)
  - final_weight_kg`, the account's current weight minus its goal weight,
  from fields `MetricsDTO` already returns. Client-only; `weight_to_shed_kg`
  itself is unchanged and still drives the engine's deficit/target-calorie
  chain correctly.
- `Trajectory.compute_weeks_to_goal` divided by `ln(1 - weekly_rate)`,
  which is exactly `0` at `weekly_rate = 0` -- a `ZeroDivisionError` on
  the very first log computed for an account at that rate. Nothing
  validates `weekly_rate` today, so this was already a latent,
  manually-triggerable bug; Phase 5.2's new `weekly_rate = 0` default for
  brand-new accounts made it the default path. Fixed with the same
  `abs(weekly_rate) < 1e-9` epsilon guard `IncrementAnalytics.py` already
  uses for its own zero-rate case, returning the same `0.0` "no
  meaningful figure" sentinel every consumer already renders as "--".
- The Log view's day view only ever matched a `"weekly"` log against its
  own literal logged date instead of its whole ISO week (README's Phase
  5.3 follow-up) -- browsing day-by-day through an already-logged week
  showed the real log on only the one day it happened to be entered, an
  empty placeholder on every other day of that week, and (since
  `refreshProjectedRow()` already bails out whenever a day has a real
  log) a stale-looking "projected" row injected on those other six days
  even though the week was already logged. `app.js`'s `filteredLogs()`
  now matches a `"weekly"` log against its whole Mon-Sun week in day
  view too (the same range check week view already used), fixing both
  symptoms at once; a `"daily"` log still only matches its own exact
  date.
- The Weight vs Goal Trajectory chart showed a fake vertical-line spike
  at every goal change (README's Phase 5.3 follow-up) -- Phase 5.3's
  period scoping correctly excludes pre-goal-change logs from the
  engine's input, but that left the new period's first row with no
  predecessor, so `weight_objective_kg` snapped to that week's actual
  weight exactly before jumping to a real weekly step the week after.
  `CompositionEngine.compute_series` gained an optional
  `initial_prev_weight_kg` context param (threaded through
  `MetricsCache.get_or_compute_series`); `MetricsSeriesService.
  compute_series_for_user` now passes in the last real log's weight from
  *before* the scoped period as trajectory context only, never
  re-included in the output, so the series stays continuous across a
  goal change.
- `admin_cut`/`admin_bulk`'s goal history showed dates backwards (README's
  Phase 5.3 follow-up) -- their first goal was always stamped
  `start_date=date.today()` at seed time (`UserManager.register`), while
  their second, backdated goal used an earlier explicit date, so goal 1
  appeared to start *after* goal 2. `UserManager.register` gained an
  optional `goal_start_date` override (defaults to today, unchanged for
  real signups); `DemoSeeder.py` now passes each account's actual
  reference-series start date for goal 1.
- The Log view could briefly render an inconsistent default state (wrong
  heading, table/placeholder visibility) right after navigating to it,
  since `navigate()` showed the view synchronously but left
  `refreshLogs()` -- which sets the nav label, heading, and table/
  placeholder visibility -- to resolve asynchronously and unawaited,
  racing against anything that inspected the view immediately (caught by
  a flaky CI failure in `Log_test.LogNavTest.
  test_default_is_todays_day_view_with_empty_placeholder`, not
  reproducible locally). `navigate()` now calls `renderLogNav()`/
  `renderFilteredLogList()` synchronously from already-known state
  (`state.logNav` always defaults to today/day-view, `state.logs` starts
  `[]`) before kicking off the fetch, so the view is always consistent
  the instant it's shown, regardless of network timing.

## [1.1.0] - 2026-07-06

Phase 4.1-4.3 of the beta-testing UX refinement round
(`things-to-improve.txt`): a consolidated hamburger nav, a simplified
dashboard-as-home summary, and a projected-weeks forecast toggle on the
Dashboard's charts.

### Changed

- Added a projected-weeks toggle to the Dashboard's charts (README's
  Phase 4.3, the third item from `things-to-improve.txt`'s first round
  of beta-testing feedback): a "Show next weeks (forecast)" checkbox
  plus a 4/8/12-week selector, inside the collapsed "Full charts &
  advanced stats" section, overlays `GET /api/projection`'s forecast
  rows onto the Weight, Body fat %, Calories, Waist & neck, and Weight
  vs. goal trajectory charts, with a dashed "Last logged" marker line at
  the last real log's date. `GET /api/projection` now also returns
  `estimated_weight`/`estimated_waist`/`estimated_neck` (the same names
  `ProjectionDTO` already used for a saved run) alongside its existing
  `MetricsDTO` fields -- purely additive, so the standalone Projection
  view is unaffected and no migration/`ENGINE_VERSION` bump was needed.
  Forecast rows already compute with `source="projected"` from the
  engine itself, so the existing small-red-dot/"(forecast)"-tooltip
  styling applies with no new styling code; the perimeters chart's
  waist/neck accessors fall back to the new fields when a row has no
  `log_id` (true for every forecast row). `charts.js`'s marker-line
  drawing (previously only on `drawMultiLineChart`, used for goal-plan-
  change markers) is now a shared `drawMarkerLines` helper also used by
  `drawLineChart`. `app.js`'s `refreshDashboardCharts()` split into a
  data-fetch half and a pure `renderDashboardCharts()` draw half, so
  toggling the control only (re)fetches the forecast itself, cached per
  weeks value. Steps and the two bar charts (fat/lean mass, gain
  quality) are deliberately left out of the overlay -- see the README's
  Phase 4.3 write-up for the scoping rationale. `sw.js`'s `CACHE_NAME`
  bumped `-v12` -> `-v13`. New Playwright coverage in
  `client/test/browser/Dashboard_test.py` (toggle on/off, a weeks-value
  change, and the marker line's presence/absence).
  - Fixed a stale-cache crash on login, caught after deploying: `enterApp()`
    unconditionally set `.checked`/`.value` on the new toggle elements,
    which threw `Cannot set properties of null` whenever a client's
    service worker served a fresh `app.js` alongside a still-cached, pre-
    Phase-4.3 `index.html` (this app's `sw.js` calls `skipWaiting()`/
    `clients.claim()`, so a page can pick up new JS before the matching
    new HTML lands). `enterApp()`'s three DOM resets and the two new
    toggle listeners now no-op instead of throwing when an element isn't
    present yet.
  - Fixed the goal-trajectory chart showing a second, unrelated dashed
    marker once the forecast toggle widened its date domain: a goal's
    `start_date` is the real wall-clock date it was created/changed
    (e.g. the very first goal, dated at registration), which can fall
    after the last logged week and previously was silently clamped to
    the chart's right edge on the real-only domain. `goalMarkers` is now
    filtered to `goal.start_date <= <last real log's date>` before
    merging in the forecast's "Last logged" marker.
  - Changed how a projected point is marked, per feedback that the
    existing styling read as a jarring color swap: `charts.js` gained a
    shared `drawPointMarker` helper -- a projected point is now hollow
    (unfilled, stroked in the series' own color) instead of a real
    point's filled dot, on both `drawLineChart` and `drawMultiLineChart`.
    Replaces an inconsistent earlier pass (a smaller dot in an unrelated
    red on `drawLineChart` only, no visual distinction at all on
    `drawMultiLineChart`); the connecting line itself is untouched, so
    only the marker shape signals "not measured yet."
- Redesigned the Dashboard into a simplified home summary (README's
  Phase 4.2, the second item from `things-to-improve.txt`'s first round
  of beta-testing feedback): three always-visible `.stat-row` card
  sections -- Weight & Body Composition (weight/body fat/lean mass,
  each with a change-vs-previous-week indicator), Calories (target
  calories, TDEE, adherence), and Goal (body fat vs. target, weight to
  goal, weeks to goal, cut/bulk direction) -- replace the full chart
  grid as the landing view. The existing 12-chart grid and the
  remaining advanced stat tiles (TEF, cumulative fat ratio, rolling
  energy-balance error, weekly-increment deviation) move into a
  collapsed-by-default `<details>` section, lazy-fetched and drawn only
  on first expand instead of on every dashboard load. A purely
  client-side change -- every figure the summary needs was already
  computed and exposed by `GET /api/metrics/latest`, `/gain-quality`,
  `/adherence`, and `/users/me`, so no server/API/DB/`ENGINE_VERSION`
  change was needed. `app.js`'s `refreshDashboard()` split into
  `refreshDashboardSummary()` (the new cheap default) and
  `refreshDashboardCharts()` (the deferred, guarded-to-run-once fetch
  for the collapsed section); `views.js` gained
  `renderWeightSummary`/`renderCaloriesSummary`/`renderGoalSummary` and
  a shared `formatDelta` helper. `sw.js`'s `CACHE_NAME` bumped
  `-v11` -> `-v12`. New Playwright coverage:
  `client/test/browser/Dashboard_test.py` (summary rendering with a
  logged change, the collapsed/lazy-loaded chart section, and a
  brand-new account's placeholder state).
  - Fixed inconsistent formatting on the collapsed section's advanced
    tiles, caught in review: Cumulative fat ratio and Energy-balance
    error (rolling) wrapped their whole value in a small `.badge` pill
    instead of the big/bold `.value` style every other tile uses, and
    Avg weekly increment crammed its goal rate onto the same long line
    as the value. Every tile's number now stays in the same big/bold
    style, moving ideal/threshold/goal context into a small subtitle
    underneath, the same way the summary sections already show a
    change/target line. On a follow-up pass, Cumulative fat ratio's
    "ideal" and Energy-balance error's "threshold" subtitles were
    further switched from a colored `badgeDelta()` pill to the same
    plain, uncolored subtitle text as every other tile's "goal"/
    "target" line -- only TEF's "flat"/"macros" mode tag (a label, not
    a good/bad judgment) still uses the colored badge.
- Consolidated the top navigation into a single hamburger menu (README's
  Phase 4.1, the first item from `things-to-improve.txt`'s first round
  of beta-testing feedback): the always-visible 8-button `.nav` row
  (Dashboard/Log/Projection/Plan/Alerts/Report/Settings/Account, plus a
  separate Logout button) is replaced by a `#nav-toggle` icon button and
  a `.nav-menu` dropdown panel listing the same eight destinations plus
  Logout, at every viewport width -- not just behind a mobile breakpoint,
  since the crowding complaint applied to desktop too. The panel reuses
  the exact same `button.nav-link[data-view]` elements `views.js`'s
  `showView()` already selects/highlights, so view-switching and
  active-tab highlighting needed no changes. `app.js` gained
  open/close/outside-click/Escape handling with focus returning to the
  toggle on close; `sw.js`'s `CACHE_NAME` bumped `-v10` -> `-v11`.
  New Playwright coverage: `client/test/browser/Nav_test.py`, driving the
  real client app end-to-end (open/close, item-click navigation, Escape,
  outside-click, logout) rather than a fixture.

## [1.0.0] - 2026-07-04

First public release, deployed via GitHub Actions: the static client on
GitHub Pages, the Flask API on Render. Covers everything built across
Phases 1-3.4: the core composition engine, the Android app (Capacitor),
and the Wave 2 bulk/volume module (cardio/gain-quality tracking, energy
reconciliation, daily/weekly logs, TEF by macronutrients, macro targets).

### Added

- `GET /api/users/me/report` and `GET /api/users/me/export` now include
  every Wave 2 read-side view: `gain_quality` (F3), `energy_balance`
  (F5), `increment_analytics` (F7), `tef` (F9) and `macro_targets` (F9+)
  -- closing the README's former "Future work" gap where a bulk account's
  trainer/nutritionist export/report only ever showed the original
  Demo_cut-era metrics. A new shared `_wave2_metrics` helper in
  `user_routes.py` computes all five from the same `services/
  composition/*` functions and reuses the exact DTOs `GET /api/metrics/*`
  already exposes -- no new computation, no `ENGINE_VERSION` implications.
  `/export`'s existing `logs`/`profile`/`goal_history`/`audit_log` fields
  (the actual import/restore contract read by `POST /api/users/me/import`)
  are unchanged; the new sections are additional, derived, read-only data.
  The printable Report view (`views.js`'s `renderReport`) gained five
  matching tables (Gain quality, Energy reconciliation, Real increment,
  TEF, Macro targets), rendered between the existing weekly series and
  open-alerts sections. `Api_test.py`'s report/export tests extended to
  assert on the new sections.

### Changed

- `data/db/DB.py`'s versioned migration runner (19 numbered migrations,
  `PRAGMA user_version` tracking) replaced with a single idempotent
  `SCHEMA` script (`CREATE TABLE IF NOT EXISTS`/`CREATE INDEX IF NOT
  EXISTS`, applied on every connect). This project keeps no real user
  data that a migration history needs to carry forward through schema
  changes -- a linear migration list only paid for itself if an existing
  database's data mattered, which it doesn't here (see the README/
  CHANGELOG for the schema's evolution as narrative history). A schema
  change going forward is just an edit to `SCHEMA`; an out-of-date local
  `justfitting.db` is deleted and recreated (`scripts/reset_db.sh` +
  `scripts/seed_demo_data.sh`), not migrated in place.
  `server/test/DB_test.py`'s migration-specific tests (idempotency of
  `.migrate()`, the v4 backfill-then-drop-columns replay) were replaced
  with one test that re-running `SCHEMA` against an already-initialized
  database doesn't error or lose data; every other DAO-level test is
  unaffected.
- `services/DemoSeeder.py` now seeds **two** demo accounts instead of one:
  `admin_cut` (Demo_cut's cut reference series, unchanged) and `admin_bulk`
  (a new Demo_bulk-resembling bulk reference series), both password
  `adminadmin`. `admin_bulk` is also given customized `EngineSettings`
  (`bmr_model="mifflin"`, `tef_mode="macros"`) and its most recent 4 weeks
  are logged at daily granularity with carb/fat/protein grams, so the
  seeded database actually exercises Phase 3/3.1/3.2/3.3/3.4's bulk-mode,
  cardio, gain-quality, energy-reconciliation, daily-granularity and
  macro-TEF/macro-target code paths end to end, not just the original
  Demo_cut cut. `LogManager.py` gained the parallel `DEMO_BULK_PROFILE`/
  `seed_bulk_reference_series` (Demo_cut's `seed_reference_series` and its
  constants are untouched -- composition_spec.md's golden reference stays
  exactly as documented). `seed_if_empty` seeds each account
  independently (idempotent per-account) and takes an optional
  `engine_settings_manager` parameter; `api/app.py` and
  `scripts/seed_demo_data.py` updated to pass it through.
  New `server/test/DemoSeeder_test.py` covers both accounts' profiles,
  idempotency, the bulk account's customized settings and mixed daily/
  macro-logged series, and the backward-compatible no-`engine_settings_
  manager` path.

### Added

- Phase 3.4: Wave 2 TEF by macronutrients — **Phase 3 (Wave 2) is now
  complete** (F1–F9 all implemented; see README's roadmap).
  - **TEF from logged macros (F9)**: optional `carbs_g`/`fat_g`/
    `protein_g` on `BodyLog` (migration 16, nullable, logged together or
    not at all — `CompositionEngine.validate_log_input` 400s a partial
    trio or a negative value). A new pure module,
    `services/composition/Tef.py` (`compute_tef_kcal`,
    `compute_tef_breakdown`), computes the directly-summed weekly TEF
    (`kappa_carbs*carbs_g + kappa_fat*fat_g + kappa_protein*protein_g`,
    defaults `0.300`/`0.135`/`1.000` kcal/g). `CompositionEngine.compute_row`
    now branches: `EngineConstants.tef_mode="macros"` (new field, default
    `"flat"`) **and** the week having macros logged switches TDEE/
    target-calories to the additive formula (`BMR+NEAT+EAT+TEF_kcal`, no
    divisor); otherwise (including a `"macros"`-mode week with nothing
    logged) the existing flat/divisor formula runs unchanged.
    `LogResampler.resample_to_weekly` extends its existing mean-of-
    logged-days convention to the three macro fields (averaging whichever
    days in a group actually logged them, `None` if none did) — this
    works because TEF is linear in each macro, so no special-casing was
    needed in the engine itself.
  - **`CompositionResult` gained `tef_kcal`/`tef_mode`** (the actual kcal
    figure and which formula this row applied), and
    `CompositionEngine.ENGINE_VERSION` bumped `1 -> 2` — the first bump
    since the engine shipped, since this is a genuine compute-chain
    branch (unlike Phase 3.1–3.3's read-side-only additions). Every log
    with no macros logged computes byte-for-byte identically to before;
    the version bump only means old `metrics_snapshots` rows (version 1)
    are never read again and recompute fresh at version 2, the same
    mechanism every prior `ENGINE_VERSION` design already relied on, just
    exercised for the first time. `metrics_snapshots` gained matching
    `tef_kcal`/`tef_mode` columns (migration 18).
  - **`GET /api/metrics/tef`** (new `Tef.compute_tef_breakdown`,
    `TefDTO`) breaks a week's TEF down by macro (grams and kcal
    contribution per macro) and reports the flat estimate alongside the
    macro figure for comparison, regardless of which one actually applied
    that week; 404s with no logs yet like every other metrics endpoint.
  - **`tef_mode` is account-level only**, not a per-request query
    parameter — `EngineConstants`/`EngineSettings` gain `tef_mode`,
    `kappa_carbs`, `kappa_fat`, `kappa_protein`, and
    `macro_kcal_mismatch_pct` (migration 17, all per-account overridable,
    historized like every other calibration field). This deliberately
    deviates from the source doc's "account setting + optional
    per-request override" wording, reusing the exact rationale Phase 3's
    `bmr_model` already established: which TEF formula applies changes
    every metrics computation for an account, not just an ephemeral
    forecast.
  - **`macro_kcal_mismatch` alert**: a new detector in
    `services/composition/Alerts.py` flags (never blocks) a week whose
    declared `intake_kcal` diverges from its macro-implied kcal
    (`4*carbs_g + 9*fat_g + 4*protein_g`, standard Atwater conversion) by
    more than `macro_kcal_mismatch_pct` (default 15%) — the source doc's
    own suggested soft coherence check, actually implemented. `detect_alerts`
    gained an optional `logs` parameter feeding it;
    `AlertSyncService.sync_alerts` now threads the series' logs through.
  - **Extension beyond either source PDF: macro targets by body mass.**
    Evidence-based per-kg-bodyweight protein/fat targets (commonly-cited
    ranges roughly 1.6–2.2 g/kg protein / 0.5–0.8 g/kg fat for a cut, and
    1.5–2.0 g/kg protein / 0.7–1.0 g/kg fat for a bulk), with carbs always
    the remainder of `target_calories` once protein/fat's kcal share is
    subtracted — never an independent target. New `protein_target_g_per_kg`
    (default `1.75`)/`fat_target_g_per_kg` (default `0.70`)/
    `macro_target_deviation_pct` (default `0.20`) `EngineConstants`/
    `EngineSettings` fields (migration 19). A new pure module,
    `services/composition/MacroTargets.py` (`compute_macro_targets`),
    exposed via `GET /api/metrics/macro-targets` (target split plus the
    actual logged split, when available). Two new alerts,
    `protein_target_deviation`/`fat_target_deviation`, flag a logged
    week's grams diverging from target by more than the threshold, only
    when that week has macros logged.
  - **Client**: the log wizard's "Energy" step gained optional Carbs/Fat/
    Protein inputs (all-or-nothing, same as the backend); the log table
    and review step show them. The Settings view gained "TEF by
    macronutrients" and "Macro targets" sections. The Dashboard gained a
    "TEF (this week)" stat tile, a flat-vs-macros TEF line chart, and a
    target-vs-actual calorie-split-by-macro **stacked-bar** chart
    (`drawMacroSplitBars`, a new `charts.js` primitive) — a stacked bar
    rather than a pie/donut, per this project's dataviz guidance (a
    part-to-whole comparison across two states reads more reliably as
    adjacent bars than as angle judgments between pie slices).
  - New `Tef_test.py`/`MacroTargets_test.py` (base cases, the flat-mode
    default, the source doc's own worked-example figure reproduced
    exactly, partial/negative-macro rejection, out-of-order input
    sorting); new cases in `CompositionEngine_test.py` (macro-mode
    switching, the automatic flat fallback, validation), `LogResampler_test.py`
    (macro averaging including the no-day-logged-it case),
    `Alerts_test.py` (`MacroKcalMismatchAlertTest`,
    `MacroTargetDeviationAlertTest`), `EngineSettingsManager_test.py`
    (bounds/validation for every new field), and `Api_test.py` (macro
    round-trip on log create/update, a 400 on a partial trio, both new
    endpoints' 404s and happy paths, the new settings fields'
    round-trip). Every pre-existing test in both suites stays green,
    proving an account that never logs macros is completely unaffected.
  - `sw.js`'s `CACHE_NAME` bumped (`-v9` -> `-v10`) for the wizard/
    Settings/Dashboard UI changes.
- Phase 3: Wave 2 bulk/volume engine foundation (see README's roadmap).
  - **Cut/bulk direction**: `GoalPlan.direction` (a `@property`, `"bulk"`
    iff `weekly_rate > 0`, no new column) is now exposed on
    `GET /api/users/me` and `GET /api/users/me/goals`. A new
    `bulk_rate_out_of_range` detector in `services/composition/Alerts.py`
    flags -- via the existing persisted/dismissible `GET /api/alerts`, not
    a blocking exception -- a bulk goal whose `weekly_rate` falls outside
    the recommended `[0.25%, 0.5%]` range (`constants.BULK_RATE_MIN/MAX`);
    `AlertSyncService.sync_alerts` now also fetches the active `GoalPlan`
    to feed it. The client's Plan view relabels the existing
    `daily_deficit_kcal` figure as "Daily surplus" (absolute value) and
    shows a Cut/Bulk direction tile for a bulk goal -- the same computed
    number, sign-flipped for display, not a new formula; the Goal history
    table (and the printable Report view's copy of it) gained a Direction
    column.
  - **Second BMR model (Mifflin-St Jeor)**:
    `EnergyModel.compute_bmr_mifflin(weight_kg, height_cm, age, sex)` joins
    the existing Cunningham `compute_bmr`. Selectable via a new
    `EngineConstants.bmr_model` field (`"cunningham"` default |
    `"mifflin"`) on the same per-account, historized `EngineSettings`
    object as every other energy-model constant -- not a per-request query
    param like `trend_model`/`activity_model`, since BMR choice affects
    every metrics computation, not just an ephemeral forecast.
    `CompositionEngine.compute_row` branches on it at the same call site
    that used to always call Cunningham.
  - **Wave 2 calibration constants**: `EngineConstants`/`EngineSettings`
    grow `delta` (fat-percentage offset, default `0.0`), `ffmi_coef`
    (default `6.3`, promoted from a literal previously hardcoded in
    `Anthropometry.py`), `w_rfm`/`w_navy`/`w_deur` (defaults
    `0.50`/`0.25`/`0.25`, promoted from fixed `constants.py` module
    globals to per-account overrides, guarded in
    `EngineSettingsManager.update_settings` to sum to `1.0` when all three
    are overridden together in the same call), `lean_tissue_kcal_per_kg`
    (default `2100`, unused until Phase 3.2's energy reconciliation) and
    `fat_ratio_ideal` (default `0.25`, unused until Phase 3.1's
    gain-quality panel) -- all reproducing today's Demo_cut numbers exactly
    by default. `BodyFat.compute_body_fat` and
    `Anthropometry.compute_ffmi_adjusted` gained trailing, defaulted
    parameters for the new weights/offset/coefficient; migration 12 adds
    the seven `engine_settings` columns. `GET`/`PUT
    /api/users/me/settings` pick up all of them automatically, since that
    route is already driven off `EngineSettingsManager.FIELDS` rather than
    a hardcoded field list; the Settings view gained a "Body-fat & BMR
    calibration" form section and a BMR-model column in the settings
    history table.
  - Every new engine parameter trails existing ones with a
    default-preserving value, so no `ENGINE_VERSION` bump was needed and
    every pre-existing golden-value test in `CompositionEngine_test.py`/
    `EnergyModel_test.py`/`BodyFat_test.py`/`Anthropometry_test.py` stays
    unchanged; a new `EngineConstantsOverrideTest` case per knob (plus a
    Mifflin-BMR bulk-profile integration test, proving `Pi_i`/
    `daily_deficit_kcal` go negative for `weekly_rate > 0`) covers the
    override path. New/extended test coverage: `BodyFat_test.py`,
    `Anthropometry_test.py`, `EnergyModel_test.py`,
    `CompositionEngine_test.py`, `Alerts_test.py` (new
    `BulkRateAlertTest`), `EngineSettingsManager_test.py` (bound rejection
    per new field, invalid-`bmr_model` rejection, the weights-sum-to-1
    guard), `GoalPlanManager_test.py` (`.direction` for both signs), and
    `Api_test.py` (settings round-trip for the new fields, `direction` in
    the goals response, an out-of-range bulk rate producing a dismissible
    alert end-to-end).
  - `sw.js`'s `CACHE_NAME` bumped (`-v5` -> `-v6`) for the Settings/Plan/
    Goal-history UI changes, same reasoning as every prior static-asset
    change.
- Phase 3.1: Wave 2 cardio input & gain-quality tracking (see README's
  roadmap).
  - **Cardio (EAT) input**: `cardio_kcal` on `body_logs` (migration 13,
    default `0`), threaded through `LogInput`, `LogManager.create_log`/
    `update_log`/`to_engine_inputs`, and `POST`/`PUT /api/logs`.
    `EnergyModel.compute_tdee`/`compute_target_calories` gained a trailing
    `eat` parameter added inside the existing divisor formula
    (`(bmr + neat + eat) / (1 - tef)`) -- `cardio_kcal=0` (every
    pre-existing log) computes byte-for-byte identically, so no
    `ENGINE_VERSION` bump was needed. The log wizard's "Energy" step
    gained a Cardio input, the log table and its review step a Cardio
    column/row.
  - **Gain-quality tracking**: a new pure module,
    `services/composition/GainQuality.py` (`compute_gain_quality`), derives
    each row's `delta_lean_kg`/`delta_fat_kg` (diffed against the previous
    row, base case `0` at the first row like `weight_delta_kg`) and their
    cumulative sums, plus `fat_ratio`/`fat_ratio_cumulative` guarded to
    `None` when the corresponding denominator is (within floating-point
    epsilon) zero -- a read-side derived view over an already-computed
    series, not a new `CompositionResult` field, mirroring how `Alerts.py`
    works. New `GET /api/metrics/gain-quality` (`GainQualityDTO`) exposes
    it, 404ing with no logs yet like `/adherence`.
  - **Dashboard gain-quality panel**: a new chart card plots each week's
    lean-vs-fat delta as a signed stacked bar via a new `charts.js`
    primitive, `drawDivergingBars` -- the existing `drawStackedBars` (used
    for fat/lean mass *levels*, always non-negative) assumes non-negative
    inputs and renders incorrectly for a loss week's negative deltas, so
    this reuses its axis/tooltip helpers but stacks each series' bar
    outward from a zero baseline instead of always upward from the
    bottom. A stat tile shows the cumulative fat ratio against the
    account's `fat_ratio_ideal` (green/warning badge).
  - New `GainQuality_test.py` (base case, cumulative sums, the
    `fat_ratio`/`None`-at-zero rule including a loss week's negative
    deltas, out-of-order input sorting, and an identity check that
    `delta_lean_kg + delta_fat_kg == weight_delta_kg` against a real
    computed series); new `EnergyModel_test.py`/`CompositionEngine_test.py`
    cases for the `eat` term; new `Api_test.py` cases (`cardio_kcal`
    create/update round-trip and its zero default, the gain-quality
    endpoint's 404 and happy path).
  - `sw.js`'s `CACHE_NAME` bumped (`-v6` -> `-v7`) for the Dashboard/log
    wizard/log table changes.
- Phase 3.3: Wave 2 daily and weekly logs coexist (see README's
  roadmap).
  - **Granularity tag**: `body_logs` gains `granularity = daily | weekly`
    (migration 15, default `'weekly'`, CHECK-constrained the same way as
    the existing `source` column), threaded through `BodyLog`/
    `BodyLogDTO`/`BodyLogDAO.create`, `LogManager.create_log`/`update_log`
    (both now reject an invalid value with a clean `ValueError` -> 400,
    unlike `source`, which has always relied solely on the DB CHECK), and
    `POST`/`PUT /api/logs`. The log wizard's first step gained a Weekly
    (default)/Daily selector; the log table and step-4 review gained a
    Granularity badge/row.
  - **Weekly-view resampling (F6)**: a new pure module,
    `services/LogResampler.py` (`resample_to_weekly`), collapses a
    mixed-granularity history into the one-row-per-week shape
    `CompositionEngine` needs. Only `granularity="daily"` rows are ever
    grouped, by ISO calendar week -- `"weekly"` rows (every log that
    existed before this phase) always pass through individually,
    byte-for-byte unchanged, regardless of weekday or spacing. This was a
    deliberate safety choice over grouping every row by calendar week
    regardless of tag, which risked merging two legitimately distinct
    weekly logs that happen to land in the same ISO week for an account
    that doesn't log on a fixed weekday. A daily group's representative
    row (median weight; mean steps/cardio/waist/neck/intake; `intake_is_
    real` true only if every grouped day's intake was real) reuses its
    max-date member's own real `log_id`, so `metrics_snapshots`'
    `UNIQUE(log_id, engine_version)` FK needed no schema change.
    `MetricsSeriesService.compute_series_for_user` calls the resampler
    once, immediately after sorting a user's logs, so every existing
    consumer (`metrics_routes.py`, `alerts_routes.py`'s
    `AlertSyncService`, `LogManager.compute_adherence`) keeps its
    existing 1:1 logs/results assumption with zero further changes;
    `GET /api/logs` is untouched and still lists every raw row. No
    `ENGINE_VERSION` bump -- resampling happens strictly before
    `LogInput` construction, same rationale as F3/F5/F7.
  - **Daily-view resampling**, the symmetric direction: `LogResampler.
    daily_view` expands a weekly log's values across every day since the
    previous log (mirrors `Projection.py`'s `activity_model="constant"`
    carry-forward, applied backward in time instead); a daily-tagged row
    emits itself only, unexpanded. Implemented and unit-tested per the
    spec's "both directions" contract, but not yet wired to a route or
    UI -- nothing in the app has a per-day display today; it's a
    ready-made building block for the still-unscheduled Phase 2.1
    automatic-steps-import idea.
  - New `LogResampler_test.py` (weekly-only passthrough is a byte-for-byte
    identity check; a full 7-day week's median/mean resampling; the
    `intake_is_real` AND-reduction rule; a partial (3-of-7-day) week; a
    lone daily row degrading to its own value; a mixed weekly+daily
    account resolving each week independently; both `daily_view` cases);
    new `LogManager_test.py` cases (granularity round-trip on create/
    update, invalid-value rejection); new `Api_test.py` cases (granularity
    round-trip and default over the API, invalid value -> 400, and an
    end-to-end case posting a full daily-logged ISO week alongside
    existing weekly history and asserting `GET /api/metrics/series`
    collapses it to one row while `GET /api/logs` still lists all 8 raw
    rows). Every pre-existing test in both suites stays green untouched,
    proving weekly-only accounts are completely unaffected.
  - `sw.js`'s `CACHE_NAME` bumped (`-v8` -> `-v9`) for the wizard/log-table
    UI changes.
- Phase 3.2: Wave 2 energy reconciliation & increment analytics (see
  README's roadmap).
  - **Energy reconciliation (F5)**: a new pure module,
    `services/composition/EnergyReconciliation.py`
    (`compute_energy_reconciliation`), compares the surplus implied by
    logged intake (`E_i - TDEE_i`) against the surplus implied by the
    *next* week's measured tissue change (`DeltaG_{i+1} * k_G +
    DeltaL_{i+1} * k_L`, reusing `GainQuality.compute_gain_quality` for
    the deltas instead of re-deriving them) and surfaces the absolute
    error plus a rolling mean of it
    (`constants.ENERGY_RECONCILIATION_WINDOW_WEEKS`, default 4 weeks,
    not per-account overridable). A read-side derived view over an
    already-computed series like `GainQuality`/`Alerts`, so no
    `ENGINE_VERSION` bump was needed. `error_kcal` (and the ingested-side
    surplus) is `None` for a week whose intake wasn't real, and for the
    most recent logged week (no next week's tissue change exists yet) --
    an inherent one-week lag, not a same-week metric. New `GET
    /api/metrics/energy-balance` (`EnergyReconciliationDTO`), 404ing with
    no logs yet like `/gain-quality`.
  - **Real-increment analytics (F7)**: a new pure module,
    `services/composition/IncrementAnalytics.py`
    (`compute_increment_analytics`), is an expanding mean of the actual
    weekly increment (`weight_delta_pct`, already computed -- no new base
    computation) over real weeks, skipping the first week's base-case
    `0.0`, plus `deviation_pct` (the fraction of the account's active
    goal rate missed, `None` when that rate is `0`). New `GET
    /api/metrics/increment-analytics` (`IncrementAnalyticsDTO`), 404ing
    with no logs or no goal plan yet.
  - **Two new alerts** extending Phase 1.3's `services/composition/Alerts.py`:
    `dirty_bulk` (a bulk goal's week whose `GainQuality.fat_ratio` exceeds
    `EngineConstants.fat_ratio_ideal`) and `recalibrate` (a week's
    reconciliation `error_kcal` above a new, per-account-overridable
    `reconciliation_error_threshold_kcal`, default `300` kcal/day) -- both
    flag via the existing persisted/dismissible `GET /api/alerts`, never
    block. `detect_alerts` gained optional `gain_quality`/`reconciliation`
    parameters (each detector is skipped if its series isn't supplied);
    `AlertSyncService.sync_alerts` now computes and threads both through.
  - **`reconciliation_error_threshold_kcal`** joins `EngineConstants`/
    `EngineSettings` (migration 14, default `300.0`, reproducing today's
    behavior for every account with no override) -- `GET`/`PUT
    /api/users/me/settings` picks it up automatically, since that route is
    driven off `EngineSettingsManager.FIELDS`; the Settings view's
    "Body-fat & BMR calibration" section gained the matching field.
  - **Dashboard**: two new chart cards (ingested-vs-tissue surplus in
    kcal/day; actual weekly increment vs. the goal rate in %, both via the
    existing `drawMultiLineChart` primitive) and two new stat tiles
    (rolling reconciliation error with a green/warning badge; average
    weekly increment against the goal rate, plus the deviation
    percentage).
  - New `EnergyReconciliation_test.py`/`IncrementAnalytics_test.py` (base
    cases, the one-week lag, assumed-intake weeks, the rolling-mean
    window, out-of-order input sorting, zero-goal-rate guard, ignoring
    projected rows); new `Alerts_test.py` cases (`DirtyBulkAlertTest`,
    `RecalibrateAlertTest`); new `Api_test.py` cases (both new endpoints'
    404s and happy paths, the new settings field's round-trip).
  - `sw.js`'s `CACHE_NAME` bumped (`-v7` -> `-v8`) for the Dashboard/
    Settings UI changes.
- Phase 1.6: recency-weighted OLS projection model. `Projection.py`'s
  `_ols` is now the uniform-weight case of a new `_weighted_ols`; a
  `trend_model: "ols" | "weighted_ols"` parameter threads through
  `project_series`/`project_series_with_inputs` alongside the existing
  `base_regression`/`activity_model`, weighting each history point by
  `WEIGHTED_TREND_DECAY ** weeks_ago` (new `constants.py` default `0.85`)
  when set to `"weighted_ols"` -- `"ols"` stays the default and is
  provably unchanged (every existing golden test is byte-identical).
  Exposed via `?trend_model=` on `GET`/`POST /api/projection`, persisted
  per saved run (`projections.trend_model`, migration v11,
  `ProjectionDAO`/domain `Projection`/`ProjectionDTO`). No client UI
  selector yet -- API-only for now, same as how `activity_model` shipped
  its backend piece first.

- Phase 1.6: Python-driven Playwright browser tests for `views.js`/`api.js`
  (`client/test/browser/`) -- not a Node.js test runner; uses the
  `playwright` dependency `environment.yml` already had, unused, ahead of
  this. A shared `LiveServer` (`live_server.py`, a Flask app on a
  `werkzeug.serving.make_server` background thread) and a minimal
  `harness_app.py` (serves the real `client/src/webapp/static/js/*` plus a
  tiny per-suite HTML fixture) let `Views_test.py` drive `views.js`'s pure
  DOM-rendering exports in a real headless-Chromium tab, and `Api_test.py`
  drive `api.js`'s exports against a real, separately-booted
  `server/src/api/app.py` instance -- an actual browser `fetch()` round
  trip, not a mock. Registers under the existing `*_test.py` glob, so
  `python -m unittest discover -s client/test -p "*_test.py"` picks it up
  automatically after a one-time `python -m playwright install chromium`.
  `.github/workflows/ci.yml` now installs Chromium
  (`playwright install --with-deps chromium`) before the client test step.

- Node.js/JDK moved into `environment.yml` as conda dependencies
  (`nodejs>=20,<21`, `openjdk=17`), replacing the earlier
  `Dockerfile.capacitor` isolation approach. Docker Desktop needs admin
  rights to install (WSL2/Hyper-V) on Windows, which isn't available on
  every machine (e.g. a restricted/non-admin account); conda envs are
  already fully user-scoped, so installing Node/the JDK the same way
  Python already is gives the same isolation with no elevated
  permissions anywhere. `scripts/install.sh`/`scripts/update.sh` (which
  already just run `conda env create|update -f environment.yml`) pick
  this up for free. README's "Android app" section was rewritten around
  this: conda for Node/JDK, the Android **command-line SDK tools** (not
  the full Studio IDE) for the SDK, building via the generated project's
  Gradle wrapper (`gradlew.bat assembleDebug`/`installDebug`) instead of
  requiring Android Studio, and testing on a real device over USB/`adb`
  as a no-admin alternative to the emulator (which needs admin to enable
  HAXM/Windows Hypervisor Platform). `android/` has been scaffolded via
  `npx cap add android` and is now committed (Capacitor's convention);
  its own generated `.gitignore` already excludes the derived
  `assets/public` copy, `local.properties`, and build outputs.

- The Android SDK setup avoids **any** global/System or User environment
  variable, not just Docker: `android/local.properties`'s `sdk.dir=` (the
  same file Android Studio itself writes) tells Gradle where the SDK is,
  `sdkmanager --sdk_root=` does the same for package installs, and
  `JAVA_HOME` is set only for the duration of a single `gradlew.bat`
  invocation (from the conda `justfitting` env) rather than persisted
  anywhere -- avoids fighting with unrelated projects on the same machine
  that might expect a different SDK/JDK. Verified end to end on a
  restricted (non-admin) Windows account: downloaded the command-line SDK
  tools, installed `platform-tools`/`platforms;android-34`/
  `build-tools;34.0.0` via `sdkmanager`, and `gradlew.bat assembleDebug`
  produced a working `app-debug.apk`.

- `npm run android:apk`: builds the debug APK and copies it to the repo
  root as `JustFitting-debug.apk` (gitignored, a build artifact) --
  for transferring the app to a phone without a live USB/`adb`
  connection at build time (email, cloud drive, messaging app, plain
  file copy). Runs `android\gradlew.bat -p android assembleDebug`
  (`-p android` instead of `cd android &&`, since chaining `cd` before
  the wrapper script misbehaved when invoked through npm's script
  shell) followed by a `copy` of the resulting APK. README documents
  enabling "Install unknown apps" on the receiving device as the last
  step. This is a debug-signed APK, fine for sideloading onto your own
  device, not for Play Store distribution.

- Phase 2: Android app packaging via **Capacitor**, replacing the
  previously-planned Trusted Web Activity (TWA)/Bubblewrap approach (see
  README's "Android app" section) with a real installable app that bundles
  the client's static `dist/` build inside the APK/AAB, rather than opening
  a hosted URL through Chrome. Root-level `package.json` (`@capacitor/core`,
  `@capacitor/cli`, `@capacitor/android`) and `capacitor.config.json`
  (`appId: com.danelarias.justfitting`, `webDir: "dist"`) added; `npm`
  scripts (`build:web`, `build:web:android`, `android:add`, `android:sync`,
  `android:open`) reuse the existing `scripts/build_static_site.py` as the
  single source of truth for the built client -- no changes needed there,
  since it already bakes the API base URL into `dist/index.html` and the
  server already reads `JUSTFITTING_CORS_ORIGINS` from the environment.
  `node_modules/` added to `.gitignore`; `android/` (generated by
  `npm run android:add`) is intentionally **not** gitignored, following
  Capacitor's convention of committing the native project. Updated the
  stale TWA/Bubblewrap references in `server/src/remote/RemoteFacade.py`'s
  and `client/src/Client.py`'s docstrings/comments. README documents the
  full workflow (install, per-target `build_static_site.py` URL for
  production/emulator/LAN, `android:sync`/`android:open`, the cleartext-HTTP
  caveat for local dev, and the CORS note for `https://localhost`), plus a
  future local/offline-mode design note (not implemented) and an
  unscheduled "Phase 2.1 -- native capabilities" ideas list (log-reminder
  notifications, native share sheet for the Report view, automatic steps
  import via Health Connect/Google Fit). No server/client runtime code
  changed -- Node.js is a dev-time packaging dependency only. Not verified
  end-to-end in this change: `npm install` / `npx cap add android` / an
  actual emulator run, which need Node.js and Android Studio locally.

- Phase 1.5: account & model completeness (see README's roadmap).
  - **Account recovery**: a direct, unverified password reset --
    `services/PasswordResetService.py`'s `reset_password(identifier,
    new_password)` looks the account up by username or email and resets
    it immediately, no email or token step. `POST /api/auth/reset-password`
    `{identifier, new_password}` (404 if no matching account) revokes
    every existing session for that user
    (`SessionDAO.delete_all_for_user`) and records a redacted `audit_log`
    entry. The existing authenticated `POST /api/users/me/password`
    (old-password required) is unchanged. The client's auth view gained a
    "Forgot password?" toggle revealing the reset form, with an inline
    disclaimer that there's no verification yet -- email-gated reset is
    unscheduled future work (README's "Known limitations"/"Future work"),
    not built now.
  - **Configurable engine constants & alert thresholds, per user**: a new
    `EngineConstants` dataclass (`services/composition/models.py`) covers
    both the energy-model constants (`tef`, `kcal_per_kg_fat`, a newly
    named `neat_step_factor`, and the implausible-change threshold) and
    the five Phase 1.3 alert thresholds, threaded as an optional
    parameter through `CompositionEngine.compute_row`/`compute_series`,
    `Alerts.detect_alerts`, and `Projection.project_series*` -- omitting
    it reproduces today's fixed `constants.py` values exactly, so every
    existing golden test is unaffected and no `ENGINE_VERSION` bump was
    needed. A new `EngineSettings` entity (migration v9,
    `data/db/EngineSettingsDAO.py`, `services/EngineSettingsManager.py`)
    historizes per-user overrides the same way `GoalPlanManager`
    historizes goal changes (deactivate-old/insert-new/audit-each-field/
    invalidate-metrics-cache). `GET`/`PUT /api/users/me/settings` and
    `GET /api/users/me/settings/history` expose it; a new "Settings"
    client view edits it (as percentages for fraction fields) and lists
    the override history.
  - **Configurable projection activity assumption**:
    `Projection.project_series_with_inputs` gained
    `activity_model="constant"` (default, today's carry-the-last-value
    behavior, unchanged) or `"trend"` (fits the same OLS trend already
    used for weight/waist/neck, clamped at 0 steps). `GET`/`POST
    /api/projection` accept `?activity=`, persisted per saved run
    (`projections.activity_model`, migration v10); the Projection view
    gained a "Steps assumption" selector.
  - **Alert-history browser**, noticed while building Phase 1.4:
    `GET /api/alerts?include_acknowledged=true` already returned the full
    history, but no UI browsed it. `api.js`'s `alerts()` now takes an
    `includeAcknowledged` flag; a new "Alerts" nav view
    (`renderAlertHistory` in `views.js`) lists every alert ever detected
    with an active/acknowledged badge, reusing the existing acknowledge
    endpoint for the still-open ones.
  - **Sex-specific formulas -- moved to "Known limitations"/"Future
    work", not implemented**: RFM and the U.S. Navy method stay
    male-calibrated for every user (Deurenberg already adjusts for sex);
    a real female Navy variant needs a hip-circumference measurement this
    app has never collected, which would mean a new logged field, wizard
    step and chart, not just a formula change. Rather than half-build it
    or schedule it into a phase, it's now an unscheduled "Known
    limitation" / "Future work" item in the README (not planned for the
    near term). Female users see an in-app disclaimer
    (`renderSexDisclaimer` in `views.js`, shown wherever body-fat figures
    are displayed) instead of a silently less-accurate number;
    `docs/composition_spec.md` and `docs/product_capabilities_spec.md`
    document the limitation.
  - 5 new server test files/additions (`EngineSettingsManager_test.py`,
    `PasswordResetService_test.py`, plus new cases in
    `CompositionEngine_test.py`, `Alerts_test.py`, `Projection_test.py`,
    and new `Api_test.py` cases covering settings CRUD/history,
    threshold-driven alert detection, the direct reset-password flow, and
    the projection activity param) and a `Client_test.py` case asserting
    the new nav/views/forms are served.
  - `docs/composition_spec.md` and `docs/product_capabilities_spec.md`
    updated to mark Phase 1.5's §14/§15/§16 items done (or moved to
    unscheduled known limitations, for the sex-specific formulas and
    email-verified reset), and the README roadmap rewritten with full
    implementation detail and new "Known limitations" / "Future work"
    sections covering both.
- Phase 1.4: adherence & reporting (see README's roadmap).
  - `GET /api/metrics/adherence` (`metrics_routes.py`, new
    `data/dto/AdherenceDTO.py`) surfaces `LogManager.compute_adherence`
    (mean `IntakeDiff` over `intake_is_real=true` rows), which previously
    existed and was unit-tested but wasn't wired to any route. The
    Dashboard's stat-tile row gained an "Adherence" tile
    (`±N kcal/day`, or "no real-intake logs yet").
  - Alerts are now persisted instead of recomputed fresh (and forgotten)
    on every `GET /api/alerts`: a new `alert_log` table (migration
    version 8 in `data/db/DB.py`), `data/domain/AlertLog.py`,
    `data/db/AlertLogDAO.py` (dedupes detections on `(user_id, type,
    date)` via `INSERT OR IGNORE`, so re-detecting the same alert is a
    no-op), and `data/dto/AlertLogDTO.py`. A new
    `services/AlertSyncService.sync_alerts` (detect → persist → list)
    is shared by `alerts_routes.py` and the new report endpoint, mirroring
    how `MetricsSeriesService` is already shared between `/api/metrics`
    and `/api/alerts`. `GET /api/alerts` now excludes acknowledged
    alerts by default (`?include_acknowledged=true` to see the full
    history) and a new `POST /api/alerts/<id>/acknowledge` dismisses
    one (404 if not found/not owned); the Dashboard's alerts panel
    gained a dismiss (×) button per alert (`views.js`'s `renderAlerts`,
    a delegated click handler in `app.js`).
  - A new `GET /api/users/me/report` (`user_routes.py`) bundles profile,
    latest metrics, adherence, the full goal-plan history, the complete
    weekly series, and open alerts into one payload — richer than the
    existing raw JSON `/export` (unchanged, still the backup/restore
    contract). A new "Report" nav view (`views.js`'s `renderReport`)
    renders it as a readable summary with a **Print / Save as PDF**
    button (`window.print()` plus a `@media print` block in
    `style.css` that hides the nav/footer/print button) — no new Python
    dependency, consistent with this repo's "no Node.js, no build step"
    architecture.
  - The historized goal-plan timeline (`GET /api/users/me/goals`,
    implemented in Phase 1.1 but unused by the client until now) is
    surfaced in two places: a "Goal history" table in the Plan view
    (`views.js`'s `renderGoalHistory`, start date/target BF/weekly
    rate/active-or-past badge) and dashed vertical markers at each
    goal-change date on the Dashboard's goal-trajectory chart.
  - `charts.js`'s `drawLineChart`, `drawMultiLineChart` and
    `drawStackedBars` were reworked from index-spaced to date-spaced
    points: a date-based x-scale (parses each row's `.date`), ~4
    gridlines/axis-tick labels per axis (asymmetric padding to make
    room for them), and hover tooltips (a per-`.chart-card`
    `.chart-tooltip` div driven by `mousemove`/`mouseleave` on the
    `<svg>`, showing the date and each series' value nearest the
    cursor) — this date-scale rework was also the prerequisite for the
    goal-change markers above. `app.js`'s chart-building calls were
    updated to pass `date` through and per-line `label`s for the
    tooltip.
  - 8 new `Api_test.py` cases: adherence with/without logs, an
    acknowledge round-trip (dismiss removes an alert from the default
    list, `?include_acknowledged=true` still shows it with
    `acknowledged_at` set), acknowledging another user's alert 404s,
    and a `GET /api/users/me/report` smoke test.
  - Fixed a pre-existing bug in `scripts/seed_demo_data.py` (unrelated
    to this phase, found while regenerating demo data for manual
    testing): it still constructed `UserManager`/`LogManager` with their
    pre-Phase-1.1 signatures, missing the `goal_plan_manager`/
    `audit_log_dao` dependencies added when `GoalPlan` was historized —
    `TypeError: UserManager.__init__() missing 1 required positional
    argument: 'goal_plan_manager'` on every run. Now wires it up the
    same way `api/app.py` does.
  - `docs/product_capabilities_spec.md` and the README roadmap updated
    to mark Phase 1.4's §14/§14.1/§16/§16.1 items done, plus an
    additive note (a dedicated alert-history browser UI — the
    `?include_acknowledged=true` data is available but nothing browses
    it yet) folded into Phase 1.5.
- Phase 1.3: alerts & feedback engine (see README's roadmap).
  - A new pure `server/src/services/composition/Alerts.py` module runs four
    detectors over an already-computed metrics series, adding no new
    computation to the compute-order chain (no `ENGINE_VERSION` bump):
    implausible week-over-week change (surfaces the existing
    `CompositionEngine.IMPLAUSIBLE_WEEKLY_CHANGE_PCT` guard, previously
    only a Python `warnings.warn`, reusing `weight_delta_pct`); stagnation/
    plateau (`STAGNATION_WEEKS` consecutive real weeks with `|dW|` under
    `STAGNATION_THRESHOLD_KG`); excessive lean-mass loss (lean mass share
    of a *net* weight loss over a `LEAN_LOSS_WINDOW_WEEKS` rolling window
    exceeding `MAX_LEAN_MASS_LOSS_SHARE`); and significant deviation from
    the goal trajectory (`|weight_gap_kg|` beyond `SIGNIFICANT_DEVIATION_KG`).
    All five thresholds are named constants in
    `composition/constants.py`.
  - `GET /api/alerts` (`server/src/api/alerts_routes.py`, `AlertDTO`)
    computes a user's series via a new shared
    `services/MetricsSeriesService.compute_series_for_user` (extracted from
    `/api/metrics`'s route, which had the identical helper inlined) and
    runs `Alerts.detect_alerts` over it — nothing new is persisted, alerts
    recompute on every read from existing logs/snapshots exactly like
    `/api/metrics/series` does.
  - The Dashboard gained an alerts panel (`#dashboard-alerts`) above the
    stat tiles: `views.js`'s new `renderAlerts` draws one bordered banner
    row per alert (red for `warning`, blue for `info`) and stays
    empty/hidden with no alerts, so a clean week costs no screen space.
    `api.js` gained `alerts()`; `app.js`'s `refreshDashboard` fetches and
    renders them alongside the existing stats/series/logs calls.
  - 11 new `Alerts_test.py` cases (pure detector logic against synthetic
    `CompositionResult` series) and 3 new `Api_test.py` cases covering
    `GET /api/alerts` end-to-end.
  - `docs/product_capabilities_spec.md` and the README roadmap updated to
    mark Phase 1.3's §14/§14.1/§16.1 items done, plus an additive note
    (alert history/acknowledgement isn't persisted yet) folded into
    Phase 1.4, and the new alert thresholds folded into Phase 1.5's
    configurable-constants item.
- Phase 1.2: visual tracking & UX completeness (see README's roadmap).
  - Dashboard chart grid grew from 4 to 7 cards: waist/neck perimeters
    (`chart-perimeters`) and daily steps (`chart-steps`) join weight, body
    fat %, fat/lean mass and calories. A new `drawMultiLineChart(svg,
    series, lines, opts)` in `client/.../js/charts.js` draws several
    labelled series (solid/dashed, own color) on one `<svg>`, generalizing
    the existing single-series `drawLineChart`. Since waist/neck/steps
    aren't in `MetricsDTO`, `app.js`'s `refreshDashboard` merges `GET
    /api/logs` (raw `BodyLogDTO`) with `GET /api/metrics/series` by
    `log_id` client-side — no server/DTO changes needed for these two
    charts.
  - A goal-trajectory chart (`chart-goal-trajectory`) plots actual weight
    (solid) against the weekly objective `Wobj` (dashed,
    `weight_objective_kg` — already computed by
    `Trajectory.compute_weight_objective` and returned in every
    `MetricsDTO` row), making real-vs-planned progress visible at a
    glance with no backend changes.
  - The flat weekly-log form (`#log-form`) is now a 4-step guided wizard
    (Date & weight → Perimeters → Energy → Review) inside one `<form>`:
    `views.js` gained `showWizardStep`/`renderLogReview`, `app.js` gates
    `Next` on the current step's inputs passing `reportValidity()` and
    renders a review summary before the final submit, which still posts
    the same payload to `POST /api/logs` — the capture UX changed, not
    the wire contract.
  - A new "Plan adjustment" view/nav item lets a user try a candidate
    target-BF/weekly-rate pair and see its effect on target calories,
    daily deficit, weeks-to-goal and goal weight *before* committing:
    `GET /api/plan/preview?target_bf=&weekly_rate=`
    (`server/src/api/plan_routes.py`, registered in `api/app.py`) reuses
    `CompositionEngine.compute_row` with a candidate `ProfileParams`
    against the latest real log, purely read-only (no persistence, no
    cache invalidation). "Commit this plan" reuses the existing `PUT
    /api/users/me` → `GoalPlanManager.create_goal_plan` (historized, as
    in Phase 1.1); the preview endpoint never writes. 4 new
    `Api_test.py` cases cover the endpoint (matches current plan with no
    overrides, reflects a candidate weekly rate, never persists a new
    goal, 404s with no logs yet).
  - `docs/product_capabilities_spec.md` and the README roadmap updated to
    mark Phase 1.2's §14/§14.1 items done, plus two additive items found
    along the way (surfacing goal-plan history in the UI; chart
    date-axis/tooltip affordances) folded into Phase 1.4.
- Phase 1.1: data model & audit hardening (see README's roadmap).
  - `GoalPlan` (`goal_plans` table, `data/db/GoalPlanDAO.py`,
    `services/GoalPlanManager.py`): target-BF/weekly-rate is now a
    historized entity instead of two mutable columns on `users` — every
    change deactivates the previous goal and inserts a new one. Migration
    v4 backfills each existing user's `target_bf`/`weekly_rate` into an
    initial active goal, then drops those two columns from `users`.
    `GET`/`PUT /api/users/me` still accept/return `target_bf`/`weekly_rate`
    at the top level (joined from the active goal), so existing clients
    are unaffected; `GET /api/users/me/goals` exposes the full history.
  - An audit trail (`audit_log` table, `data/db/AuditLogDAO.py`) records
    every profile-field edit (`UserManager.update_profile`), goal-plan
    change (`GoalPlanManager.create_goal_plan`), and body-log field edit
    (`LogManager.update_log`): user, entity, field, previous/new value,
    timestamp, and engine version where applicable. `GET
    /api/users/me/audit-log` exposes it; it's also folded into `GET
    /api/users/me/export`.
  - Composition results are now cached per log, keyed by `(log_id,
    engine_version)` (`metrics_snapshots` table,
    `data/db/MetricsSnapshotDAO.py`, `services/MetricsCache.py`), so
    historical values stay reproducible if `CompositionEngine.ENGINE_VERSION`
    ever changes, instead of always recomputing on read. A user's cache is
    invalidated on any log create/update/delete or goal-plan change, so
    the next read recomputes and repopulates it. `MetricsDTO` now carries
    `log_id`/`engine_version`.
  - Forecast runs can now be persisted (`projections` table,
    `data/db/ProjectionDAO.py`, `services/ProjectionService.py`,
    `Projection.project_series_with_inputs`): `POST /api/projection`
    saves the current forecast under a `run_id`; `GET /api/projections`
    lists saved runs and `GET /api/projections/<run_id>` retrieves one, so
    a forecast can be inspected later without recomputing. `GET
    /api/projection` (the live, unsaved preview) is unchanged.
  - `docs/product_capabilities_spec.md` and the README roadmap updated to
    mark Phase 1.1's §14/§15/§16 items done.
- Phase 1: server-client web app.
  - Composition engine (`server/src/services/composition/`) implementing
    the verified "Demo_cut" spec — anthropometry, body-fat estimators
    (RFM/Navy/Deurenberg), energy model (BMR/NEAT/TDEE/target calories),
    goal trajectory, and OLS-based weekly projection.
  - SQLite-backed data layer with a linear migration runner, DAOs for
    users/sessions/body logs, and domain/DTO models.
  - Services layer: `UserManager` (profile CRUD, PBKDF2 password hashing),
    `AuthService` (bearer sessions with sliding expiry), `LogManager`
    (weekly log CRUD, real-vs-assumed intake, Demo_cut reference demo seed).
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

### Fixed

- Bumped the PWA service worker's `CACHE_NAME` again
  (`client/src/webapp/static/sw.js`, `justfitting-shell-v4` -> `-v5`) for
  Phase 1.5's new Settings/Alerts nav views and forgot/reset-password
  forms, same reasoning as the bumps below.
- Bumped the PWA service worker's `CACHE_NAME` again
  (`client/src/webapp/static/sw.js`, `justfitting-shell-v3` -> `-v4`) for
  Phase 1.4's new Report view, goal-history table, and reworked charts,
  same reasoning as the bumps below.
- Bumped the PWA service worker's `CACHE_NAME` again
  (`client/src/webapp/static/sw.js`, `justfitting-shell-v2` -> `-v3`) for
  Phase 1.3's Dashboard alerts panel, same reasoning as the `-v1` -> `-v2`
  bump below.
- Bumped the PWA service worker's `CACHE_NAME`
  (`client/src/webapp/static/sw.js`, `justfitting-shell-v1` ->
  `-v2`) so browsers that had the app open before Phase 1.2 stop
  serving the stale cached shell (old flat log form, no Plan tab,
  missing charts) after an update. The service worker's
  stale-while-revalidate strategy only refreshes its cache in the
  background on the *next* request; a byte change to `sw.js` is what
  makes the browser install a new worker and purge the old cache.
  **Any future change to the static JS/CSS/HTML app shell needs the
  same version bump**, or returning users will keep seeing stale
  assets until they manually clear site data.
