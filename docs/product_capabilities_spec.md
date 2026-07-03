# JustFitting product capabilities spec (source: "Documento Final", v2.0)

This records, in English, the product-capability sections of the
consolidated technical spec (`docs/JustFitting_Documento_Final.pdf`,
2026-07-02, v2.0) that go beyond the calculation engine already covered by
`docs/composition_spec.md`. Section numbers below (§14–§16) refer to the
original document, kept for traceability.

**Formula cross-check**: every equation in the source document (§3–§13,
Anexo A) was compared against `server/src/services/composition/` and
matches exactly — RFM, Navy, Deurenberg, the weighted body-fat mean, mass
partition, BMR/NEAT/TDEE/target-calories, the trajectory/deficit/weeks-to
-goal chain, and the OLS projection block. No engine changes are needed;
what follows are the additional product capabilities the source document
specifies (§14), its recommended data model (§15) and its validation
rules (§16) that are **not yet implemented**.

## §14. Functional capabilities

| Capability | Technical description | Status in this repo |
| --- | --- | --- |
| User management | Registration, login, **account recovery**, body profile, goal params. | Registration/login/profile done; goal params now historized (`GoalPlan`, Phase 1.1). Account recovery is a direct, unverified reset (Phase 1.5, `POST /api/auth/reset-password {identifier, new_password}`, `services/PasswordResetService.py`) -- no email or token step. Email-verified reset is recorded as unscheduled future work, not a current-phase item; see the README's "Known limitations" / "Future work". |
| Weekly logging | **Guided** capture of weight/waist/neck/intake/steps; edit **with a change audit trail**. | CRUD done; capture is now a 4-step guided wizard (Phase 1.2: Date & weight → Perimeters → Energy → Review, same `POST /api/logs` contract); audit trail done (Phase 1.1, `audit_log`). |
| Calculation engine | Auto-recompute of BMI, FFMI, fat estimators, fat/lean mass, targets and calories, with a versioned dependency order. | Done — `CompositionEngine.ENGINE_VERSION`, compute order documented. |
| Visual tracking | Charts for weight, **perimeters (waist/neck)**, fat %, fat/lean mass, calories, **and steps**. | Done (Phase 1.2): waist/neck and steps charts added to the Dashboard (`chart-perimeters`, `chart-steps`), alongside the pre-existing weight/fat%/fat-lean-mass/calories charts. |
| Projection | Configurable linear forecast **and a comparison between the real trajectory and the goal trajectory**, clearly marking forecast vs. measured. | Forecast + `real`/`projected` badging done; forecast runs can be persisted and re-fetched (Phase 1.1). The real-vs-goal trajectory comparison is now a Dashboard chart (Phase 1.2, `chart-goal-trajectory`: actual weight vs. the weekly objective `Wobj`, `weight_objective_kg` already in `MetricsDTO`). |
| Energy plan | BMR/NEAT/TDEE/daily-deficit/target-calories; **adherence analysis computed only over real intake**. | Estimates done, cached per log (Phase 1.1, `MetricsCache`). A **Plan adjustment** view (Phase 1.2) previews the effect of a candidate target-BF/weekly-rate on target calories and weeks-to-goal before committing (`GET /api/plan/preview`, `server/src/api/plan_routes.py`), reusing `CompositionEngine.compute_row` with no persistence. `LogManager.compute_adherence` is now exposed via `GET /api/metrics/adherence` (Phase 1.4, `AdherenceDTO`) and shown as a Dashboard stat tile. |
| Alerts & feedback | Warnings for incoherent measurements, **stagnation**, **excessive lean-mass loss**, or **significant deviation** from plan. | Done (Phase 1.3): `services/composition/Alerts.py` detects all four over an already-computed series (implausible change now a structured alert, not just `warnings.warn`; stagnation over `STAGNATION_WEEKS` real weeks; excessive lean loss over a `LEAN_LOSS_WINDOW_WEEKS` window; deviation via `weight_gap_kg`), exposed via `GET /api/alerts` and a Dashboard alerts panel. Detections are now persisted (Phase 1.4, `alert_log` table, `AlertLogDAO`, deduped on `(user_id, type, date)`) instead of only computed fresh on every read, so an alert can be acknowledged (`POST /api/alerts/<id>/acknowledge`) and stays gone across reads; the Dashboard panel gained a dismiss button. |
| Export | **Technical reports/summaries for the user, a trainer, or a nutritionist.** | JSON export (`/export`) still includes goal history and the audit log (Phase 1.1) alongside profile/logs, unchanged as the backup/restore contract. A new `GET /api/users/me/report` (Phase 1.4) bundles profile, latest metrics, adherence, goal history, the full weekly series and open alerts into a presentation-oriented payload, rendered by a new client "Report" view with a **Print / Save as PDF** button (browser print, no new PDF dependency). |

### §14.1. Recommended user flow

1. Sign-up & profile: height, birthdate, sex, target body fat, weekly rate.
2. First log: weight/waist/neck/intake/steps; the app computes the baseline.
3. Recurring log: weekly update; metrics recomputed and compared to the previous week.
4. Progress review: dashboard with evolution, deviations, and projection to goal.
5. **Plan adjustment**: recommended target-calorie change and its expected impact on weeks remaining.

Steps 1–3 exist today (Account, Log, Dashboard views), step 3's capture is
now the guided wizard (Phase 1.2). Step 5's dedicated plan-adjustment flow
also exists now (Phase 1.2, the Plan view + `GET /api/plan/preview`). Step
4's deviation callouts (flagging actual-vs-`Wobj` divergence beyond a
margin, not just charting it) are now done too (Phase 1.3, the Dashboard
alerts panel's `deviation` alert type). The goal-plan history behind step
5 is now also visible in the UI (Phase 1.4, a "Goal history" table in the
Plan view plus goal-change markers on the Dashboard's goal-trajectory
chart), not just returned by the API.

## §15. Recommended data model

| Entity | Key fields | Purpose | Status |
| --- | --- | --- | --- |
| `UserProfile` | `user_id, height_cm, sex, birthdate, units, created_at` | Stable user data. | Implemented (`data/domain/UserProfile.py`); `target_bf`/`weekly_rate` moved off this table into `GoalPlan` (Phase 1.1). |
| `GoalPlan` | `goal_id, user_id, target_bf, weekly_rate, start_date, active` | Goal/rate configuration, **historized** (a user can have had several goal periods). | Implemented (Phase 1.1: `data/db/GoalPlanDAO.py`, `services/GoalPlanManager.py`, `GET /api/users/me/goals`). |
| `BodyLog` | `log_id, user_id, date, weight_kg, waist_cm, neck_cm, intake_kcal, intake_is_real, steps` | Raw weekly record. `intake_is_real` distinguishes logged vs. assumed intake. | Implemented (`data/db/BodyLogDAO.py`). |
| `CalculatedMetrics` | `log_id, age, bmi, ffmi, ffmi_adj, rfm, navy, deurenberg, body_fat, fat_mass, lean_mass` | Persisted composition metrics, for audit. | Implemented (Phase 1.1: `metrics_snapshots` table, `data/db/MetricsSnapshotDAO.py`, `services/MetricsCache.py`), combined with `EnergyPlan` into one snapshot row per `(log_id, engine_version)` as the spec allows. |
| `EnergyPlan` | `log_id, bmr, neat, tdee, weekly_target_weight, daily_deficit, target_calories, intake_diff` | Persisted energy metrics. | Implemented — see `CalculatedMetrics` above (same snapshot row). |
| `Projection` | `projection_id, user_id, projected_date, estimated_weight, estimated_waist, estimated_neck, source_model, base_regression, activity_model` | Saved forecast runs; `base_regression` records whether the fit used real-only or real+projected data, `activity_model` (Phase 1.5) whether steps were held constant or trend-fit. | Implemented (Phase 1.1: `data/db/ProjectionDAO.py`, `services/ProjectionService.py`, `POST /api/projection` to save, `GET /api/projections[/​<run_id>]` to retrieve; `activity_model` column added in Phase 1.5). `GET /api/projection` (ephemeral preview) is unchanged. |
| `EngineSettings` | `settings_id, user_id, tef, kcal_per_kg_fat, neat_step_factor, implausible_weekly_change_pct, stagnation_weeks, stagnation_threshold_kg, lean_loss_window_weeks, max_lean_mass_loss_share, significant_deviation_kg, start_date, active` | Per-user overrides of the energy-model constants and Phase 1.3 alert thresholds, historized like `GoalPlan`. | Implemented (Phase 1.5: `data/db/EngineSettingsDAO.py`, `services/EngineSettingsManager.py`, `GET`/`PUT /api/users/me/settings`, `GET /api/users/me/settings/history`). No row means the fixed `constants.py` defaults apply. |

`CalculatedMetrics` and `EnergyPlan` are persisted as a single
`metrics_snapshots` row per log (as the spec explicitly allows), keyed by
`(log_id, engine_version)` so historical values stay reproducible if the
engine's formulas or compute order ever change.

## §16. Validations, assumptions and limitations

- **Units**: height/waist/neck in cm, weight in kg, calories in kcal/day, steps as a daily average. — Already followed.
- **Alert thresholds**: the Phase 1.3 alert thresholds (`STAGNATION_WEEKS`, `STAGNATION_THRESHOLD_KG`, `LEAN_LOSS_WINDOW_WEEKS`, `MAX_LEAN_MASS_LOSS_SHARE`, `SIGNIFICANT_DEVIATION_KG`) are named constants in `constants.py`, same as the energy-model ones below. — Done (Phase 1.5): per-user overridable via `GET`/`PUT /api/users/me/settings`, historized like a goal plan (`engine_settings` table, `EngineSettingsManager`); a user with no override gets the exact `constants.py` defaults (`is_default: true`).
- **Sex and formulas**: Deurenberg varies by sex; **RFM and U.S. Navy are implemented with male-only constants**. The spec calls for either sex-specific variants or an explicit declared scope. — Explicit scope declared (Phase 1.5): RFM/Navy stay male-calibrated for every user; a female-specific U.S. Navy variant needs a hip-circumference measurement this app doesn't collect. Rather than schedule this into a phase, it's recorded as an unscheduled "Known limitation" / "Future work" item in the README (not planned for the near term), and female users see an in-app disclaimer (`renderSexDisclaimer`) instead of a silent inaccuracy.
- **Minimum measurements**: RFM/Navy require waist; Navy requires `waist > neck`. — Enforced (`CompositionEngine.validate_log_input`).
- **Real vs. assumed intake**: mark intake as real or assumed; compute adherence only over real data. — `intake_is_real` field and `compute_adherence` exist and are now surfaced via `GET /api/metrics/adherence` and a Dashboard stat tile (Phase 1.4).
- **Projections**: TREND results are linear estimates; always show as forecast, never as measurement; the regression base must be an explicit, documented choice. — Done (`base_regression`, `source` badges).
- **Activity in projection**: steps are held constant in the forecast zone; the activity assumption should be configurable. — Done (Phase 1.5): `activity_model="constant"` (default, unchanged behavior) or `"trend"` (OLS-fits steps the same way as weight/waist/neck), via `?activity=` on `GET`/`POST /api/projection` and a Projection-view selector; persisted per saved run (`projections.activity_model`).
- **Calories**: the 7700 kcal/kg factor, 10% TEF, and the NEAT formula are approximations and should be parametrized. — Done (Phase 1.5): all three (`kcal_per_kg_fat`, `tef`, `neat_step_factor`) are part of the same per-user `EngineConstants` override as the alert thresholds above.
- **Health**: not a medical diagnosis; include disclaimers and refer to professionals where appropriate. — Done (client footer disclaimer).
- **Audit**: every update must retain date, user, previous value, new value, and the calculation-engine version. — Implemented (Phase 1.1): the `audit_log` table records profile, goal-plan, and body-log edits (`services/GoalPlanManager.py`, `UserManager.update_profile`, `LogManager.update_log`), exposed via `GET /api/users/me/audit-log`.

### §16.1. Suggested coherence rules

- No negative weight/height/waist/neck/intake/steps. — Enforced.
- Flag a weekly weight change above a configurable threshold as suspicious. — Done (Phase 1.3): `IMPLAUSIBLE_WEEKLY_CHANGE_PCT` is now also surfaced as a structured `GET /api/alerts` warning, not just a Python `warnings.warn`. Alerts are now persisted and acknowledgeable (Phase 1.4) rather than only recomputed fresh on every read.
- Require `waist > neck` before running the U.S. Navy formula. — Enforced.
- Separate real measurements from projected records via a `source = real | projected` field. — Enforced.
- Save the formula/engine version used at every recalculation, to reproduce historical results. — Implemented (Phase 1.1): every `metrics_snapshots` row is keyed by `(log_id, engine_version)`, and `MetricsDTO` surfaces `engine_version` per row.

See `README.md`'s roadmap section for how these gaps are grouped into
implementation phases.

## Oleada 2 — new functional capabilities (source: `docs/JustFitting_Oleada2_Sergio.pdf`, v1.0)

Everything above (§14–§16) comes from the original "Danel" (cut/deficit)
spec and is implemented. This section records a **second** source
document — a bulk/volume ("Sergio") profile verified against a separate
spreadsheet — that specifies eight new capabilities. F1, F4 and F8 (the
Phase 3 foundation) are now implemented; F2/F3 (Phase 3.1) and F5/F6/F7
(Phase 3.2/3.3) remain planned. See `docs/composition_spec.md`'s "Oleada 2" section for the full
formulas, including its "Formula reconciliation" note: the source
document's literal TDEE/target-calorie formulas look different from
Danel's (TEF as a multiplier, a different weight basis for the surplus),
but working through the physiology (TEF as % of *total* TDEE, not of
non-food expenditure) shows the existing divisor formula was already
correct, and the real difference is just one additive term — cardio/EAT,
`0` by default. Read that reconciliation before scoping F1/F4 below; it's
why their "planned action" cells say "extend," not "fork."

A **third** source document, `docs/JustFitting_TEF_Macronutrientes.pdf`
(v1.0), specifies a ninth capability (F9, below): it replaces the flat
10% TEF approximation the reconciliation above justifies with a value
computed from actually-logged carb/fat/protein grams, once F6's daily
granularity is in place. It's the biggest single accuracy upgrade in
Oleada 2 — two accounts with identical calories/steps/weight but
different macro splits get genuinely different, physiologically-grounded
energy estimates instead of the same flat number.

### Capabilities (F1–F8)

| # | Capability | Technical description | Status | Planned action |
| --- | --- | --- | --- | --- |
| F1 | Surplus/bulk mode | Goal engine generalized to a positive weekly rate `rho > 0`; weekly/daily surplus in kcal (the same `Pi_i`/deficit figure already computed, sign-flipped and relabeled); recommended-range validation `[0.25%, 0.5%]`. | **Done (Phase 3).** `GoalPlan.direction` (`@property`, `"bulk"` iff `weekly_rate > 0`) exposed on `GoalPlanDTO`/`ProfileDTO`. A new `bulk_rate_out_of_range` detector in `Alerts.py` flags (doesn't block) a bulk goal outside `[BULK_RATE_MIN, BULK_RATE_MAX]` (`constants.py`, `0.25%`–`0.5%`), surfaced via the existing persisted/dismissible `GET /api/alerts`. The client's Plan view relabels the existing `daily_deficit_kcal` as "Daily surplus" (absolute value) for a bulk goal — no new surplus formula. | New `direction = cut \| bulk` derived from `weekly_rate`'s sign; display-layer relabeling of the existing `weekly_deficit_kcal`/`daily_deficit_kcal`, no new surplus formula (see `composition_spec.md`'s reconciliation note). |
| F2 | Cardio (EAT) as input | New field, kcal spent on exercise, on either a daily or weekly log (F6); adds one term (`EAT_i`, default `0`) to the existing TDEE/target-calorie formulas. | Not implemented — `BodyLog` has no exercise field. | Add `cardio_kcal` to `BodyLog`; include as `+ EAT_i` in `EnergyModel.py`'s existing TDEE/TargetCal formulas. With `EAT_i=0` every existing log computes identically to today. |
| F3 | Gain quality (lean/fat partition) | Weekly and cumulative lean-vs-fat split of the weight *change*; ideal ratio 25/75 (fat share ≤ 25%). | Not implemented — the app tracks levels (fat %, fat/lean mass) but not the composition of week-over-week *change*. | New `GainQuality` engine output (`delta_lean_kg`, `delta_fat_kg`, cumulative, `fat_ratio`); reuses the already-computed `weight_delta_kg`. |
| F4 | Second BMR model (Mifflin–St Jeor) | `bmr_model = cunningham \| mifflin`, selectable; Mifflin depends only on weight/height/age (correctly sex-specific, unlike RFM/Navy), and avoids feeding BMR off a lean-mass estimate that's comparatively noisy early in a bulk. | **Done (Phase 3).** `EnergyModel.compute_bmr_mifflin`; selectable via `EngineConstants.bmr_model` (`"cunningham"` default \| `"mifflin"`), historized per-account like every other `EngineSettings` field (`GET`/`PUT /api/users/me/settings`), not a per-request query param like `trend_model`/`activity_model` — BMR choice affects every metrics computation, not just an ephemeral forecast. | Add `Mifflin` to `EnergyModel.py`; expose `bmr_model` the same way `trend_model`/`activity_model` are exposed today. Feeds the same shared TDEE/TargetCal formula as F2 — a model choice, not a separate formula. |
| F5 | Energy reconciliation ("Error") | Compares surplus implied by intake (`E_i - TDEE_i`) against surplus implied by the *next* week's tissue change; flags a large gap for recalibration. | Not implemented — no cross-check exists between the energy model and the measured composition change. | New `EnergyReconciliation` module; new `k_L` (lean-tissue kcal/kg) constant; inherently one-week-lagged (needs week `i+1`). |
| F6 | Daily/weekly log coexistence | Optional daily capture (weigh-in, steps, cardio); a weekly *view* of daily logs takes the median weight / mean steps+cardio for the week; a daily *view* of a weekly log copy-pastes that log's values across every day since the previous one. Both directions, same mechanism. | Not implemented — `BodyLog` is one row per week with no granularity tag. | Add `granularity = daily \| weekly` to `BodyLog` (same pattern as the existing `source = real \| projected` tag) instead of a separate `DailyEntry` entity; `CompositionEngine` resolves whichever weekly view it needs on the fly. Degrades to today's single-value behavior for an account that only ever logs weekly. Also the natural data path for the README's unscheduled "automatic steps import" idea (Phase 2.1). |
| F7 | Real-increment analytics | Actual week-over-week weight increment vs. the goal rate; running mean; normalized deviation. | Partial — `weight_delta_pct` already computes the same underlying figure (`composition_spec.md` confirms the identity); no running mean or goal-relative deviation is surfaced. | Derived-analytics layer only, no new base computation: `mean(weight_delta_pct)` and `Desv_i = (rho - weight_delta_pct_i) / rho`. |
| F8 | Per-user calibration constants | Fat-percentage offset `delta`, FFMI coefficient, lean-tissue kcal/kg `k_L`, ideal fat-ratio ceiling — all account-overridable, historized like existing `EngineSettings`. | **Done (Phase 3).** `EngineConstants`/`EngineSettings` gained `delta` (default `0.0`), `ffmi_coef` (default `6.3`, promoted from the `Anthropometry.py` literal), `w_rfm`/`w_navy`/`w_deur` (defaults `0.50/0.25/0.25`, promoted from `constants.py` module globals, guarded to sum to `1.0` when all three are overridden together), `lean_tissue_kcal_per_kg` (default `2100`, unused until Phase 3.2's F5), and `fat_ratio_ideal` (default `0.25`, unused until Phase 3.1's F3) — all historized via migration 12, `GET`/`PUT /api/users/me/settings` picks them up automatically (`FIELDS`-driven route). | Extend `EngineSettings`/`EngineConstants` with `fat_offset` (default `0.0`), `ffmi_coef` (default `6.3`, promoting today's `Anthropometry.py` literal to a named, overridable constant), `lean_tissue_kcal_per_kg` (default `2100`), `fat_ratio_ideal` (default `0.25`), and, going a step beyond the source doc: promote `bf_weight_rfm`/`bf_weight_navy`/`bf_weight_deurenberg` (today `constants.py` module globals, defaults `0.50/0.25/0.25`, shared by every account) into the same per-account override set, since Sergio's doc already establishes that the weighted body-fat formula needs a personal correction and there's no principled reason the offset is overridable but the weights it's added to aren't. Defaults must reproduce today's Danel numbers exactly. |

### Capability F9 — TEF by macronutrients (source: `docs/JustFitting_TEF_Macronutrientes.pdf`)

| # | Capability | Technical description | Status | Planned action |
| --- | --- | --- | --- | --- |
| F9 | TEF by macronutrients | Daily TEF = `kappa_C*carbs_g + kappa_G*fat_g + kappa_P*protein_g` (kcal), weekly TEF = mean of the week's days; replaces the flat `/(1-TEF)` estimate additively (`TDEE = BMR+NEAT+EAT+TEF`) once macros are logged; falls back to flat per-week when they aren't. | Not implemented — `BodyLog`/daily rows have no macro fields, and `EnergyModel.py` has only the flat TEF path. | Add `carbs_g, fat_g, protein_g` to the daily-granularity log row (F6) — no new entity needed, since F6 already generalized daily capture onto `BodyLog` itself. New `Tef` module (`daily_tef`, `weekly_tef`, not persisted — derived on read). `EnergyModel` gains `tef_mode = flat \| macros`. See `composition_spec.md`'s F9 section for the full formulas and a numeric inconsistency flagged in the source doc's own worked example. |

### New/changed data model

| Entity | Change | Purpose |
| --- | --- | --- |
| `BodyLog` | `+ cardio_kcal, + granularity (daily \| weekly), + carbs_g, fat_g, protein_g` (macros only meaningful on daily-granularity rows) | F2/F6/F9: one table, no separate `DailyEntry`/`DailyMacroEntry` entity — F6's granularity tag was already the right foundation for F9's macro fields too. |
| `GoalPlan` | `direction` derived from `weekly_rate`'s sign (no new column needed, unless a UI wants to store the user's intent independent of the numeric rate) | F1: cut vs. bulk labeling. |
| `EngineSettings` | `+ fat_offset, bf_weight_rfm, bf_weight_navy, bf_weight_deurenberg, ffmi_coef, lean_tissue_kcal_per_kg, fat_ratio_ideal, kappa_C, kappa_G, kappa_P, tef_mode` | F8/F9, all historized/overridable like the Phase 1.5 fields. |
| `CalculatedMetrics` snapshot | `+ delta_lean_kg, delta_fat_kg, fat_ratio, fat_ratio_cumulative, energy_reconciliation_error, tef_kcal, tef_mode` (bulk-mode rows only) | F3/F5/F9 outputs, same snapshot-per-`(log_id, engine_version)` pattern as today. |

### API additions (planned)

- `GET /api/metrics/gain-quality` — F3 partition and ratios.
- `GET /api/metrics/energy-balance` — F5 ingested-vs-tissue surplus and error.
- `GET /api/metrics/tef` — F9 daily and weekly TEF, broken down by macro.
- `bmr_model=cunningham|mifflin` parameter on the metrics/projection endpoints that compute BMR — F4.
- `POST /api/logs` accepts `cardio_kcal`, `granularity`, and (on daily rows) `carbs_g, fat_g, protein_g`; a daily-granularity log is posted the same way a weekly one is today, just tagged and dated per-day (F6/F9).
- `tef_mode=flat|macros` parameter alongside `bmr_model` on the same metrics/projection endpoints — F9.
- `EngineSettings` read/write endpoints (`GET`/`PUT /api/users/me/settings`, already existing) extended with the F8 fields.

### Validations, assumptions and limitations (Oleada 2)

- **One shared formula, not a fork**: the source doc's literal TDEE/
  target-calorie formulas look structurally different from Danel's (TEF as
  a multiplier; a this-week weight basis for the surplus), but
  `composition_spec.md`'s "Formula reconciliation" works through why the
  existing divisor-based formula is the physiologically correct one (TEF
  as % of *total* TDEE) and why the existing `Pi_i`-based deficit already
  generalizes to a surplus unmodified. The only real addition is `+ EAT_i`
  (default `0`). Implement F1/F2/F4 as extensions of the shared
  `EnergyModel.py` chain, not a parallel `direction=bulk` codepath — with
  `EAT_i=0` every existing log computes byte-for-byte identically, so
  `CompositionEngine_test.py`'s golden values don't drift and
  `ENGINE_VERSION` doesn't need to bump for this alone. Recomputing the
  source doc's own worked example with the corrected formula gives ≈2796
  kcal vs. its printed 2724.5 kcal (≈2.6%, from the TEF fix) — an
  intentional, documented deviation from the literal spreadsheet, not a
  bug to chase.
- **Defaults preserve Danel exactly**: `fat_offset=0.0`, `ffmi_coef=6.3`,
  and `bf_weight_rfm/navy/deurenberg=0.50/0.25/0.25` are the new defaults,
  not Sergio's calibrated `0.02`/`6.1` — a user with no override must see
  identical numbers to today. Same "no row = today's behavior" contract as
  every other `EngineSettings` field. Sergio's `0.02`/`6.1` are one
  account's calibration, not a claimed universal constant, per the source
  doc's own caution — and note his document doesn't actually change the
  RFM/Navy/Deurenberg weights, only adds the offset; making the weights
  overridable too is this repo's own generalization, not something the
  source doc asked for.
- **Body-fat weights must sum to 1**: if `bf_weight_rfm`,
  `bf_weight_navy`, and `bf_weight_deurenberg` are overridden, validate
  they sum to `1.0` (within tolerance) so `BF_i` stays a proper weighted
  mean rather than silently rescaling.
- **Reconciliation is one-week-lagged**: F5's `Error_i` needs week `i+1`'s
  data and can never be computed for the most recent logged week — an
  a-posteriori check, not a same-week metric.
  Recommend a rolling-mean view, per the source doc.
- **Gain-quality ratio is undefined at zero weight change**: `FatRatio_i`
  divides by `delta_lean + delta_fat` (== `weight_delta_kg`); guard
  against `weight_delta_kg == 0` rather than computing a `NaN`/divide error, and treat the ratio as meaningful only when the week is a net
  gain (`weight_delta_kg > 0`).
- **Granularity is per-log, not per-account**: F6's `granularity` tag lives
  on each `BodyLog` row, not as an account-level setting — a user can log
  daily some weeks and weekly others, and both resolve correctly (median
  weight / mean steps+cardio for a weekly *view* of a daily week; the
  logged value copy-pasted across the days a weekly log covers, for a
  daily *view*). An account that only ever logs weekly sees no behavior
  change; `median(w^(1), ...)` degrades to a single value with one
  weigh-in, identical to today.
- **Mifflin's sex term is already correct**: `+5` (male) / `-161`
  (female) is a real per-sex coefficient, unlike RFM/Navy's male-only
  constants — F4 does not inherit the existing "Known limitations"
  disclaimer, and should not display it.
- **New alerts** (extending Phase 1.3's `Alerts.py`): fat ratio above
  `fat_ratio_ideal` on a bulk week ("dirty bulk"); reconciliation error
  above a configurable threshold ("recalibrate"); `weekly_rate` outside
  the recommended bulk range `[0.25%, 0.5%]`.
- **F9 depends on F6, not the other way around**: macro-based TEF only
  has data to compute from on daily-granularity log rows (F6); a week
  logged only at weekly granularity has no per-day macro grams, so
  `tef_mode` silently resolves to `"flat"` for that week even on an
  account set to `"macros"` — never a blocking error.
- **F9's worked example doesn't fully reconcile numerically**: the source
  doc's own TDEE integration example (`BMR=1892.5, NEAT=159.4,
  EAT=478.6, TEF=288.3` stated to sum to `2854.8`) actually sums to
  `2818.8` by the stated formula — a ~36 kcal gap, most likely from
  rounding the displayed subtotals before printing. Treat the additive
  formula (`composition_spec.md`, F9) as authoritative, not that specific
  printed total, when writing a golden-reference test for this feature.
- **F9's weekly average over partial weeks is an open decision**: the
  source doc raises, but doesn't resolve, whether a week's TEF should
  average only the days with macros logged or require a complete week.
  Recommend averaging whatever's logged (minimum 1 day), consistent with
  how F6's median weight already degrades gracefully with partial data.
- **F9's coefficients are Atwater-standard and literature averages**:
  `kappa_C/G/P` (or the underlying `e_m`/`tau_m`) don't account for
  alcohol or fiber, and vary by individual — hence overridable, same
  historized mechanism as every other engine constant. A soft (flag, not
  block) coherence check between declared `kcal` and `4*carbs_g +
  9*fat_g + 4*protein_g` is worth surfacing, not enforcing.
- **Health disclaimer** (unchanged scope): energy balances and fat
  estimates remain population-level approximations, not medical or
  nutritional prescriptions — same footer disclaimer applies to Oleada 2
  figures.

See `README.md`'s roadmap for how F1–F9 are grouped into phases.
