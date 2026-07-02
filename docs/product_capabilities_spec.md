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
| User management | Registration, login, **account recovery**, body profile, goal params. | Registration/login/profile done; account recovery (forgot-password) missing. |
| Weekly logging | **Guided** capture of weight/waist/neck/intake/steps; edit **with a change audit trail**. | CRUD done; capture is a flat form, not guided; no audit trail. |
| Calculation engine | Auto-recompute of BMI, FFMI, fat estimators, fat/lean mass, targets and calories, with a versioned dependency order. | Done — `CompositionEngine.ENGINE_VERSION`, compute order documented. |
| Visual tracking | Charts for weight, **perimeters (waist/neck)**, fat %, fat/lean mass, calories, **and steps**. | Weight, fat %, fat/lean mass and calories charted; waist/neck and steps charts missing. |
| Projection | Configurable linear forecast **and a comparison between the real trajectory and the goal trajectory**, clearly marking forecast vs. measured. | Forecast + `real`/`projected` badging done; no real-vs-goal trajectory comparison chart. |
| Energy plan | BMR/NEAT/TDEE/daily-deficit/target-calories; **adherence analysis computed only over real intake**. | Estimates done; `LogManager.compute_adherence` exists but isn't exposed via API/UI. |
| Alerts & feedback | Warnings for incoherent measurements, **stagnation**, **excessive lean-mass loss**, or **significant deviation** from plan. | Not implemented (only a silent `warnings.warn` for an implausible weekly change). |
| Export | **Technical reports/summaries for the user, a trainer, or a nutritionist.** | Only raw JSON export/import exists; no formatted report. |

### §14.1. Recommended user flow

1. Sign-up & profile: height, birthdate, sex, target body fat, weekly rate.
2. First log: weight/waist/neck/intake/steps; the app computes the baseline.
3. Recurring log: weekly update; metrics recomputed and compared to the previous week.
4. Progress review: dashboard with evolution, deviations, and projection to goal.
5. **Plan adjustment**: recommended target-calorie change and its expected impact on weeks remaining.

Steps 1–3 exist today (Account, Log, Dashboard views). Step 4's deviation
callouts and step 5's dedicated plan-adjustment flow do not exist yet.

## §15. Recommended data model

| Entity | Key fields | Purpose | Status |
| --- | --- | --- | --- |
| `UserProfile` | `user_id, height_cm, sex, birthdate, units, created_at` | Stable user data. | Implemented, but `target_bf`/`weekly_rate` live on this same table. |
| `GoalPlan` | `goal_id, user_id, target_bf, weekly_rate, start_date, active` | Goal/rate configuration, **historized** (a user can have had several goal periods). | Not implemented — today's single mutable `target_bf`/`weekly_rate` on `UserProfile` has no history. |
| `BodyLog` | `log_id, user_id, date, weight_kg, waist_cm, neck_cm, intake_kcal, intake_is_real, steps` | Raw weekly record. `intake_is_real` distinguishes logged vs. assumed intake. | Implemented (`data/db/BodyLogDAO.py`). |
| `CalculatedMetrics` | `log_id, age, bmi, ffmi, ffmi_adj, rfm, navy, deurenberg, body_fat, fat_mass, lean_mass` | Persisted composition metrics, for audit. | Computed on read, not persisted/cached. |
| `EnergyPlan` | `log_id, bmr, neat, tdee, weekly_target_weight, daily_deficit, target_calories, intake_diff` | Persisted energy metrics. | Computed on read, not persisted/cached. |
| `Projection` | `projection_id, user_id, projected_date, estimated_weight, estimated_waist, estimated_neck, source_model, base_regression` | Saved forecast runs; `base_regression` records whether the fit used real-only or real+projected data. | Computed on demand (`Projection.project_series`), never persisted. |

The spec allows `CalculatedMetrics`/`EnergyPlan` to be cached rather than
mandatory, as long as they stay recomputable from the raw inputs and the
engine version — which is already true here. Persisting them (and
`Projection`) becomes valuable once the audit trail (§16 "Auditoría") and
historized `GoalPlan` are in place.

## §16. Validations, assumptions and limitations

- **Units**: height/waist/neck in cm, weight in kg, calories in kcal/day, steps as a daily average. — Already followed.
- **Sex and formulas**: Deurenberg varies by sex; **RFM and U.S. Navy are implemented with male-only constants**. The spec calls for either sex-specific variants or an explicit declared scope. — Not yet addressed; currently silently male-only.
- **Minimum measurements**: RFM/Navy require waist; Navy requires `waist > neck`. — Enforced (`CompositionEngine.validate_log_input`).
- **Real vs. assumed intake**: mark intake as real or assumed; compute adherence only over real data. — `intake_is_real` field and `compute_adherence` exist; not surfaced in the API/UI.
- **Projections**: TREND results are linear estimates; always show as forecast, never as measurement; the regression base must be an explicit, documented choice. — Done (`base_regression`, `source` badges).
- **Activity in projection**: steps are held constant in the forecast zone; the activity assumption should be configurable. — Steps are hardcoded constant; not configurable.
- **Calories**: the 7700 kcal/kg factor, 10% TEF, and the NEAT formula are approximations and should be parametrized. — Named in `constants.py`, but fixed at the code level, not user/admin-configurable.
- **Health**: not a medical diagnosis; include disclaimers and refer to professionals where appropriate. — Done (client footer disclaimer).
- **Audit**: every update must retain date, user, previous value, new value, and the calculation-engine version. — Not implemented; no audit log exists.

### §16.1. Suggested coherence rules

- No negative weight/height/waist/neck/intake/steps. — Enforced.
- Flag a weekly weight change above a configurable threshold as suspicious. — Exists internally (`IMPLAUSIBLE_WEEKLY_CHANGE_PCT`) but only as a Python warning, not a user-facing alert.
- Require `waist > neck` before running the U.S. Navy formula. — Enforced.
- Separate real measurements from projected records via a `source = real | projected` field. — Enforced.
- Save the formula/engine version used at every recalculation, to reproduce historical results. — `ENGINE_VERSION` constant exists but isn't stored per computed row.

See `README.md`'s roadmap section for how these gaps are grouped into
implementation phases.
