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
| User management | Registration, login, **account recovery**, body profile, goal params. | Registration/login/profile done; goal params now historized (`GoalPlan`, Phase 1.1); account recovery (forgot-password) missing. |
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
| `Projection` | `projection_id, user_id, projected_date, estimated_weight, estimated_waist, estimated_neck, source_model, base_regression` | Saved forecast runs; `base_regression` records whether the fit used real-only or real+projected data. | Implemented (Phase 1.1: `data/db/ProjectionDAO.py`, `services/ProjectionService.py`, `POST /api/projection` to save, `GET /api/projections[/​<run_id>]` to retrieve). `GET /api/projection` (ephemeral preview) is unchanged. |

`CalculatedMetrics` and `EnergyPlan` are persisted as a single
`metrics_snapshots` row per log (as the spec explicitly allows), keyed by
`(log_id, engine_version)` so historical values stay reproducible if the
engine's formulas or compute order ever change.

## §16. Validations, assumptions and limitations

- **Units**: height/waist/neck in cm, weight in kg, calories in kcal/day, steps as a daily average. — Already followed.
- **Alert thresholds**: the Phase 1.3 alert thresholds (`STAGNATION_WEEKS`, `STAGNATION_THRESHOLD_KG`, `LEAN_LOSS_WINDOW_WEEKS`, `MAX_LEAN_MASS_LOSS_SHARE`, `SIGNIFICANT_DEVIATION_KG`) are named constants in `constants.py`, same as the energy-model ones below — not yet user/admin-configurable (Phase 1.5).
- **Sex and formulas**: Deurenberg varies by sex; **RFM and U.S. Navy are implemented with male-only constants**. The spec calls for either sex-specific variants or an explicit declared scope. — Not yet addressed; currently silently male-only.
- **Minimum measurements**: RFM/Navy require waist; Navy requires `waist > neck`. — Enforced (`CompositionEngine.validate_log_input`).
- **Real vs. assumed intake**: mark intake as real or assumed; compute adherence only over real data. — `intake_is_real` field and `compute_adherence` exist and are now surfaced via `GET /api/metrics/adherence` and a Dashboard stat tile (Phase 1.4).
- **Projections**: TREND results are linear estimates; always show as forecast, never as measurement; the regression base must be an explicit, documented choice. — Done (`base_regression`, `source` badges).
- **Activity in projection**: steps are held constant in the forecast zone; the activity assumption should be configurable. — Steps are hardcoded constant; not configurable.
- **Calories**: the 7700 kcal/kg factor, 10% TEF, and the NEAT formula are approximations and should be parametrized. — Named in `constants.py`, but fixed at the code level, not user/admin-configurable.
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
