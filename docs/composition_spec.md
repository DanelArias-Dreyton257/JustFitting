# JustFitting composition model — the "Danel" spec

This is the authoritative maths spec the engine in
`server/src/services/composition/` is tested against
(`server/test/CompositionEngine_test.py` is the golden acceptance test).
If a formula here and the code ever disagree, treat this document and the
golden reference values below as the source of truth.

## Inputs

Static per-user params: height `H` (cm), sex `g` (1 = male, 0 = female),
`birthdate`, target body-fat fraction `tau` (e.g. 0.15), weekly target rate
`r` (fraction/week, negative = loss, e.g. -0.005).

Weekly inputs for row `i`: date `t_i`, weight `W_i` (kg), waist `c_i` (cm),
neck `n_i` (cm), intake `E_i` (kcal/day), steps `s_i` (/day).

`round(x, k)` rounds to `k` decimals; `log10` is decimal log; `ln` is
natural log; `floor` truncates to an integer.

## Anthropometry

```
age_i      = floor((t_i - birthdate) / 365.25)
BMI_i      = round(W_i / (H/100)^2, 2)
FFMI_i     = MM_i / (H/100)^2
FFMI_adj_i = FFMI_i + 6.3 * (1.80 - H/100)
```

## Body-fat estimators (fractions; male constants for RFM & Navy)

```
RFM_i  = (64 - 20 * (H / c_i)) / 100
Navy_i = (495 / (1.0324 - 0.19077*log10(c_i - n_i) + 0.15456*log10(H)) - 450) / 100   # needs c_i > n_i
Deur_i = (1.2*BMI_i + 0.23*age_i - 10.8*g - 5.4) / 100
BF_i   = 0.50*RFM_i + 0.25*Navy_i + 0.25*Deur_i   # weighted mean, the headline %
```

**Known limitation (male-only RFM/Navy):** RFM and the US Navy method above
use their male-form constants for every user, regardless of `g` (sex) --
only Deurenberg adjusts for sex. The real female Navy formula needs a
hip-circumference measurement (`waist + hip - neck`, different regression
constants) that JustFitting doesn't collect anywhere in its data model, so
fixing this means a new logged field, not just a formula change. This is
unscheduled future work, not planned for the near term -- see the README's
"Known limitations" / "Future work" sections. A client-side disclaimer is
shown to female users instead (`renderSexDisclaimer` in `views.js`) so the
limitation is visible rather than silent.

## Mass partition & distance to target

```
FatMass_i  = round(W_i * BF_i, 2)          # MG
LeanMass_i = round(W_i * (1 - BF_i), 2)    # MM -> feeds FFMI, BMR, W_final
AJ_i       = BF_i - tau                     # +ve => above target
```

## Energy model (`TEF = 0.10`; EAT assumed 0)

```
BMR_i        = 500 + 22 * LeanMass_i                     # Cunningham
NEAT_i       = 0.5 * W_i * (s_i / 1000)
TDEE_i       = (BMR_i + NEAT_i) / (1 - TEF)
TargetCal_i  = (BMR_i + NEAT_i - DailyDeficit_i) / (1 - TEF)
IntakeDiff_i = E_i - TargetCal_i
```

`TEF` is really a % of *intake*, but here it's applied as a divisor on
`BMR + NEAT`. `TEF`, the `7700` kcal/kg constant and the NEAT step factor
(`0.5` above) default from `services/composition/constants.py`, never
inlined in routes, and are now also overridable per user (Phase 1.5): see
`services/composition/models.EngineConstants` (also carries the Phase 1.3
alert thresholds) and `services/EngineSettingsManager.py`, which historizes
overrides the same way `GoalPlanManager` historizes goal changes. Omitting
an override reproduces the fixed `constants.py` values exactly.

## Goal & trajectory (base cases at the first row, marked below)

```
dW_i     = W_i - W_{i-1}                       # base: 0 at i=1
pct_i    = (W_i - W_{i-1}) / W_{i-1}           # base: 0 at i=1
Wobj_i   = W_{i-1} * (1 + r)                    # Wobj_1 = W_1
K_i      = W_i - Wobj_i
Pi_i     = W_{i-1} - Wobj_i                     # weight to shed this step; base 0 at i=1
WeeklyDeficit_i = Pi_i * 7700                   # ~7700 kcal per kg of fat
DailyDeficit_i  = WeeklyDeficit_i / 7
Wfinal_i = LeanMass_i / (1 - tau)               # weight at target BF, lean preserved
Weeks_i  = ln(W_i / Wfinal_i) / ln(1 - r)       # NB ln(1 - r); with r=-0.005 => ln(1.005)
```

## Compute order (no circular references)

inputs -> age, BMI -> RFM/Navy/Deurenberg -> BF -> Fat/Lean ->
(FFMI, BMR, Wfinal) -> Wobj -> Pi -> WeeklyDeficit -> DailyDeficit ->
TDEE, TargetCal -> IntakeDiff.

This ordering is versioned (`CompositionEngine.ENGINE_VERSION`): bump it
whenever the order or a formula it depends on changes in a way that would
alter previously-computed rows.

## Projection (forecast) — future weeks

```
t_i = t_{i-1} + 7 days
W_i, c_i, n_i = OLS_linear_forecast(history vs date, at t_i)   # spreadsheet TREND() equivalent
s_i           = held CONSTANT (carry last value), or the same OLS trend as W/c/n
                if `activity_model="trend"` (Phase 1.5, default stays "constant")
E_i           = TargetCal_{i-1}, with intake_is_real = false
# then recompute ALL derived metrics for row i exactly as for real rows
```

`base_regression` chooses whether the OLS fit uses real records only
(`"real_only"`, the default, for stability) or an expanding window that
also includes prior forecasts (`"real_and_projected"`). Projected rows are
always labelled as forecasts, never as measurements.

`trend_model` (Phase 1.6) chooses how the linear trend itself is fit:
`"ols"` (default, unweighted, exactly today's behavior) or `"weighted_ols"`,
which weights each history point by `WEIGHTED_TREND_DECAY ** weeks_ago`
(`constants.py`, default `0.85`) so recent weeks influence the slope more
than older ones — still a straight-line fit, just recency-biased, applied
identically to weight/waist/neck (and to steps too when
`activity_model="trend"`).

**Intake semantics:** once intake is set to `TargetCal_{i-1}` (assumed, not
logged), `IntakeDiff` compares a recommendation against a recommendation
and is ~0 by construction. Adherence must only be computed over rows where
`intake_is_real = true`.

## Validation guards

Reject non-positive weight/height/waist/neck/intake/steps; require
`c_i > n_i` before evaluating `Navy_i`; flag (not block) an implausible
weekly weight change above a configurable threshold
(`CompositionEngine.IMPLAUSIBLE_WEEKLY_CHANGE_PCT`).

## Golden reference values

Profile: `H=176, sex=1, birthdate=2001-08-22, target_bf=0.15, weekly_rate=-0.005`.

Last real record **2026-06-26** — inputs `W=90.7, waist=80.0, neck=35.0, steps=5000`:

```
BMI 29.28 | RFM 0.2000 | Navy 0.1519 | Deurenberg 0.2446 | BF 0.1991 (19.91%)
FatMass 18.06 kg | LeanMass 72.64 kg | FFMI 23.45 | FFMI_adj 23.70
BMR 2098.08 | NEAT 226.75 | TDEE 2583.14 | TargetCal 2027.03 | IntakeDiff -12.73
Wobj 90.545 | K +0.155 | dW -0.3 | DailyDeficit 500.5 | Wfinal 85.459
Weeks 11.93 | AJ +0.0491 (4.91 pp)
```

First record **2025-12-28** — input `W=97.0` (waist 91.0, neck 38.5):

```
BF 0.2459 (24.59%) | FatMass 23.85 | LeanMass 73.15 | BMI 31.31
```

Tolerance: ±0.01 (±0.5 kcal for calorie figures). Also verified: the
base-case row (`dW=pct=Pi=0`, `Wobj_1=W_1`, deficit 0 => `TargetCal==TDEE`),
the Navy guard (`waist <= neck` raises `ValueError`), and a projection case
(dates advance by 7, `intake_is_real=false`, metrics recompute).

## Oleada 2 — bulk/volume model (the "Sergio" spec)

Source: `docs/JustFitting_Oleada2_Sergio.pdf` (v1.0, 2026-07-02). This is a
second worked profile on top of the same core estimators above (RFM, Navy,
Deurenberg, NEAT) but for a **surplus/bulk** goal instead of a deficit/cut
one, plus new inputs and metrics the source spreadsheet computes that
`CompositionEngine` doesn't yet. Profile: `H=194, sex=1,
birthdate=2001-04-05, target_bf=0.15, weekly_rate=+0.005` (recommended
range `[0.0025, 0.005]`, i.e. +0.25%–0.5%/week).

New weekly input: cardio `a_i` (kcal spent on exercise, EAT — assumed 0 in
the Danel model).

**This section documents the source formulas as given, including where
they genuinely diverge from the implemented Danel chain above (not just
relabeled) — see "Formula reconciliation" below before implementing.**

A third source document, `docs/JustFitting_TEF_Macronutrientes.pdf` (F9,
below), refines this further: it replaces the flat 10% TEF approximation
this section's formulas use with one computed from actually-logged
carb/fat/protein grams. It's documented last (F9) because it depends on
F6's daily granularity, but conceptually it's a precision upgrade to F4's
energy model, not a separate feature — read it once F1–F8 make sense.

### Fat-formula weights and offset, and FFMI coefficient (generalizes the existing formulas)

```
BF_i       = w_rfm*RFM_i + w_navy*Navy_i + w_deur*Deur_i + delta   # weights default 0.50/0.25/0.25, delta default 0.0 -- reproduces Danel exactly
FFMI_adj_i = FFMI_i + ffmi_coef * (1.80 - H/100)                    # ffmi_coef default 6.3 (today's hardcoded value)
```

The source doc's own Sergio profile actually keeps the **same** weights
Danel uses (`0.50/0.25/0.25` — confirmed in the Anexo's Excel formula, `P
=(M*0.5+N*0.25+O*0.25)+0.02`) and only adds the offset `delta`. But
`BF_WEIGHT_RFM`/`BF_WEIGHT_NAVY`/`BF_WEIGHT_DEURENBERG` today are fixed
module constants in `constants.py`, shared by every account, not part of
`EngineConstants`/`EngineSettings` at all — unlike everything else the
engine tunes per user. Since Sergio's document already demonstrates one
account needing a personal correction to this exact formula, promote the
three weights to per-user-overridable fields alongside `delta`, not just
add the offset: a future third profile might genuinely need a different
RFM/Navy/Deurenberg balance (e.g. a body type where one estimator tracks
worse), and there's no reason to special-case "offset is per-user but the
weights aren't" once one of the three is already overridable. **Guard**:
validate `w_rfm + w_navy + w_deur == 1.0` (within tolerance) when all
three are overridden together, so `BF_i` stays a proper weighted mean and
doesn't silently become a differently-scaled quantity.

`delta`, `w_rfm`/`w_navy`/`w_deur`, and `ffmi_coef` (Sergio's value `6.1`,
vs. the `6.3` currently hardcoded as a literal in `Anthropometry.py`, not
even in `constants.py`) are all new per-user-overridable constants.
**Defaults must stay `delta=0.0`, `w_rfm=0.50`, `w_navy=0.25`,
`w_deur=0.25`, and `ffmi_coef=6.3`** so an account with no override
reproduces today's Danel numbers exactly, same contract as every other
`EngineSettings` field (Phase 1.5) — Sergio's `0.02`/`6.1` are his own
calibration, applied only via his account's override, never as the new
default.

### F1 — Surplus/bulk mode (done)

```
W_i^obj = W_{i-1} * (1 + rho)          # unchanged from Danel's Wobj_i
Pi_i    = W_{i-1} - W_i^obj = -rho * W_{i-1}   # unchanged from Danel's Pi_i; negative when rho > 0
```

`rho` is the same signed weekly-rate field as Danel's `r`
(`GoalPlan.weekly_rate`); `rho > 0` is a bulk goal, `rho < 0` a cut goal —
no new field needed for the rate itself, only a derived `direction =
"bulk" | "cut"` label from its sign. Validate `rho` against the
recommended range `[0.25%, 0.5%]` when `direction == "bulk"` and surface a
(non-blocking) warning outside it, mirroring
`IMPLAUSIBLE_WEEKLY_CHANGE_PCT`'s flag-not-block pattern.

Danel's existing `Pi_i`/`DailyDeficit_i` chain already generalizes to
`rho > 0` without a new formula: `Pi_i` simply goes negative, so
`DailyDeficit_i` (`= Pi_i * k_G / 7`) goes negative too — a "negative
deficit," which is a surplus. **The UI-facing "weekly/daily
surplus" figure a bulk account sees is this same, already-computed
`weekly_deficit_kcal`/`daily_deficit_kcal` pair, sign-flipped and
relabeled "surplus" for display** — not a second, independently-computed
number. See "Formula reconciliation" below for why this is the right
call, and why it supersedes the source doc's literal `Superavit_i^sem =
rho * W_i * k_G` (which uses this week's weight, `W_i`, rather than
`Pi_i`'s `W_{i-1}` basis — a difference the reconciliation section
resolves by reusing the existing, tested mechanism rather than forking a
second one for a numerically close but distinct quantity).

### F2 — Cardio (EAT) input (done)

`cardio_kcal` (`a_i`) is a new `body_logs` column (migration 13, default
`0`), threaded through `LogInput`/`LogManager`/`POST`/`PUT /api/logs` and
folded into `EnergyModel.compute_tdee`/`compute_target_calories` as the
`+ EAT_i` term the "Formula reconciliation" section below already
anticipated -- see F4 for where it enters the energy chain, and F6 for its
(still planned) daily-aggregated form.

### F3 — Gain quality (lean/fat partition of the *change*) (done)

```
DeltaL_i    = LeanMass_i - LeanMass_{i-1},   DeltaG_i    = FatMass_i - FatMass_{i-1}
DeltaL_i^ac = DeltaL_i + DeltaL_{i-1}^ac,    DeltaG_i^ac = DeltaG_i + DeltaG_{i-1}^ac   # base 0 at i=1, same convention as dW_1=0
FatRatio_i    = DeltaG_i    / (DeltaL_i    + DeltaG_i)
FatRatio_i^ac = DeltaG_i^ac / (DeltaL_i^ac + DeltaG_i^ac)
```

Note `DeltaL_i + DeltaG_i == weight_delta_kg` (`dW_i`, already computed by
`Trajectory.py`) exactly, since `LeanMass_i + FatMass_i == W_i` by
construction — F3 doesn't need a new "total change" input, only the
lean/fat split of the `dW_i` JustFitting already has. `FatRatio_i` is
undefined (guard, don't divide) when `dW_i == 0`; it's only a meaningful
"how clean is this gain" signal when `dW_i > 0`. Ideal ceiling: `FatRatio_i
<= 0.25` (new `fat_ratio_ideal` constant).

Implemented as a new pure module, `services/composition/GainQuality.py`
(`compute_gain_quality`), rather than new `CompositionResult` fields — it's
a read-side derived view over an already-computed series (mirroring
`Alerts.py`), not a change to the compute-order chain, so no
`ENGINE_VERSION` bump was needed. Denominators near zero (floating-point
noise, not a true `dW_i == 0`) are treated as zero via a small epsilon,
same "guard, don't divide" intent as the exact-zero case. Exposed via `GET
/api/metrics/gain-quality`.

### F4 — Second BMR model (Mifflin–St Jeor) (done)

```
BMR_i^Cunn    = 500 + 22 * LeanMass_i                              # existing, unchanged
BMR_i^Mifflin = 10*W_i + 6.25*H - 5*age_i + 5                      # male; female variant uses -161 in place of +5
```

Selectable per request/account (`bmr_model = cunningham | mifflin`), same
pattern as `trend_model`/`activity_model` (Phase 1.5/1.6). Unlike RFM/Navy,
Mifflin already has a correct sex-specific term (`+5` / `-161`), so it
doesn't inherit the "Known limitations" male-only-formula caveat above.

### Formula reconciliation — TDEE and target calories generalize with one added term, not a fork

The source document's literal TDEE/target-calorie formulas look
structurally different from Danel's, but working through *why* each side
computes what it computes shows they should converge to a single
generalized formula — one new additive term (`EAT_i`), not two parallel
codepaths. (An earlier draft of this section proposed forking bulk mode
into a separate formula path; this replaces that with the reconciled
version below.)

**Why TEF is a divisor, not a multiplier.** Physiologically,
`TDEE = BMR + NEAT + EAT + TEF` (four additive components; TEF is the
thermic effect of food, energy spent digesting what's eaten). Population
studies put TEF at roughly 10% of *total* daily expenditure. Substituting
`TEF_i = TEF * TDEE_i` into that identity and solving for `TDEE_i`:

```
TDEE_i = BMR_i + NEAT_i + EAT_i + TEF * TDEE_i
TDEE_i * (1 - TEF) = BMR_i + NEAT_i + EAT_i        # BMR+NEAT+EAT are the other 90% of TDEE
TDEE_i = (BMR_i + NEAT_i + EAT_i) / (1 - TEF)
```

The divisor form is the algebraically correct one for "TEF is 10% of
TDEE" — Danel's existing formula already has this right; the source
doc's `(BMR + NEAT + EAT) * (1 + TEF)` instead treats TEF as 10% of
*non-food* expenditure, a different (and physiologically less
faithful) quantity. **Both directions use the divisor form.**

**Why EAT was 0 in Danel and matters for Sergio.** The two goals tolerate
error in opposite directions. A cut is safe to *underestimate* expenditure
for: assuming `EAT=0` when the user actually exercises only makes the
prescribed target calories lower than their true adjusted TDEE, which
just makes the cut a bit more conservative — it never derails the goal. A
bulk is not safe to underestimate expenditure for: the same `EAT=0`
assumption would under-prescribe calories relative to what a lifter
burns, working directly against "eat enough to grow." That's the real
reason F2 (explicit cardio logging) matters specifically for bulk
accounts, not a different formula — the formula was always `... + EAT_i`,
Danel's version just always evaluated it at 0.

**Why BMR model differs by goal, separately from TDEE.** A cut assumes
weight lost is predominantly fat, so Cunningham (driven by the current
lean-mass estimate, which is expected to stay roughly stable) is a
reasonable BMR base. A bulk expects lean mass itself to grow, which makes
Cunningham's input less stable early in a bulk — before gains show up in
the fat/lean split, the lean-mass estimate feeding it is comparatively
noisy. Mifflin–St Jeor (F4), driven by total weight/height/age instead,
sidesteps that circularity, which is why it's offered as an option for
bulk accounts rather than a Cunningham replacement. This is a selection
choice (`bmr_model`), independent of the TDEE/TEF fix above.

**The reconciled formula** — one shared chain, `EAT_i` (`cardio_kcal`,
defaulting to `0`) is the only new term, `BMR_i` is whichever model is
selected, and the existing `Pi_i`-based deficit/surplus (F1 above,
unchanged) is reused verbatim for both directions:

```
TDEE_i      = (BMR_i + NEAT_i + EAT_i) / (1 - TEF)
TargetCal_i = (BMR_i + NEAT_i + EAT_i - DailyDeficit_i) / (1 - TEF)   # DailyDeficit_i negative => surplus, exactly as F1 describes
```

With `EAT_i = 0` (every existing Danel log) this is **byte-for-byte
identical** to today's implemented formula — no golden-reference drift,
no `ENGINE_VERSION` bump, no forked codepath. `direction=bulk` only
changes which `bmr_model` defaults in and starts collecting `cardio_kcal`;
the arithmetic was already general enough.

**Divergence from the source doc's literal worked numbers.** Recomputing
§5's example with this reconciled formula (Mifflin BMR, `EAT=0`, holding
the deficit/surplus magnitude at the doc's own ≈437 kcal/day since a
single week's `W_i` and `W_{i-1}` are close) gives target calories of
**≈2796 kcal**, not the source doc's **2724.5 kcal** — a ≈2.6% difference
attributable entirely to the TEF-divisor correction above (`/0.9` vs.
`*1.1`). This is an intentional, reasoned deviation from the literal
spreadsheet, not a transcription error — implementers should expect not
to exactly reproduce the PDF's own worked total once this fix is applied,
and that's by design.

`Wfinal_i = LeanMass_i / (1 - tau)` and `Weeks_i = ln(W_i / Wfinal_i) /
ln(1 - rho)` are unchanged from the Danel spec and apply as-is to
`rho > 0` (the source doc doesn't redefine either).

Everything in this reconciliation is about the best estimate of TEF
*without* macro data — a percentage-of-TDEE approximation, justified
above. **F9 below removes the approximation entirely** for weeks with
carb/fat/protein logged, replacing the divisor with a directly-summed
kcal figure. Treat this section's divisor formula as the permanent
`tef_mode="flat"` fallback, not a placeholder to eventually replace app-wide.

### F5 — Energy reconciliation ("Error") (done)

```
Superavit_i^ingerido = E_i - TDEE_i
Superavit_i^tejido    = (DeltaG_{i+1} * k_G + DeltaL_{i+1} * k_L) / 7     # note i+1: next week's deltas
Error_i                = abs(Superavit_i^ingerido - Superavit_i^tejido)
```

`k_L` (lean-tissue energy density, default `2100 kcal/kg`, new constant —
Danel's chain never needed one) is separate from `k_G` (`KCAL_PER_KG_FAT`,
already `7700`, unchanged). **The tissue side uses week `i+1`'s deltas**:
`Error_i` can only be computed once the *following* week's log exists, and
never for the most recent logged week — an inherent one-week-lagged,
a-posteriori validation, not a same-week metric. A rolling mean of `Error_i`
is surfaced alongside the raw value (source doc's own suggestion).

Implemented as a new pure module, `services/composition/EnergyReconciliation.py`
(`compute_energy_reconciliation`) — a read-side derived view over an
already-computed series, reusing `GainQuality.compute_gain_quality` for the
`DeltaG_{i+1}`/`DeltaL_{i+1}` deltas rather than re-deriving them, so no
`ENGINE_VERSION` bump was needed. `Superavit_i^ingerido`/`Error_i` are `None`
for a week whose intake wasn't real (`intake_is_real=False`); the tissue
side (mass-only) is computed regardless, since weight/waist/neck are always
real when logged. The rolling-mean window
(`constants.ENERGY_RECONCILIATION_WINDOW_WEEKS`, default 4) is a fixed
display-smoothing constant, not per-account overridable, unlike the new
`reconciliation_error_threshold_kcal` (default `300` kcal/day) the
"recalibrate" alert below uses. Exposed via `GET /api/metrics/energy-balance`.

### F6 — Daily and weekly logs coexist; each view resamples the other (done)

Revised design (beyond the source doc, which only specifies the
weekly-from-daily direction): rather than a separate `DailyEntry` table
that exists purely to feed a required weekly rollup, a log row carries a
`granularity = daily | weekly` tag (`body_logs`, migration 15, default
`'weekly'`, CHECK-constrained like the existing `source` column), the same
way it already carries `source = real | projected` — one table, one new
discriminator, not a new entity. Every consumer resolves whichever
granularity it needs from whatever's actually stored, in both directions:

Implemented as a new pure module, `services/LogResampler.py`
(`resample_to_weekly`, `daily_view`) — not under `services/composition/`,
since it operates on persisted `BodyLog` rows and runs strictly *before*
`LogInput` construction, not on the engine's own compute chain; no
`ENGINE_VERSION` bump was needed. `MetricsSeriesService.compute_series_for_user`
calls `resample_to_weekly` once, immediately after sorting a user's raw
logs, so every downstream consumer (`metrics_routes.py`, `alerts_routes.py`
via `AlertSyncService`, `LogManager.compute_adherence`) keeps receiving a
1:1 logs/results pair exactly as before — none of them needed to change.
`GET /api/logs` (the raw log table) is untouched and always lists every
individual row, daily or weekly.

**Safety rule, load-bearing for backward compatibility**: only rows
tagged `granularity="daily"` are ever grouped. A `"weekly"` row (the
default, and every row that existed before this feature) always passes
through as its own week, byte-for-byte unchanged, regardless of what
weekday it falls on or how close together consecutive logs are —
identical to today's behavior for every existing account. Grouping *all*
rows by calendar week regardless of tag was considered and rejected: an
account that doesn't log on a fixed weekday could have two legitimately
distinct weekly logs land in the same ISO week and get wrongly merged — a
real regression risk. Daily-tagged rows are grouped by ISO calendar week
(`date.isocalendar()[:2]`); the representative row for each group is the
max-date member (a real `log_id`, so `metrics_snapshots`'s
`UNIQUE(log_id, engine_version)` FK stays valid with no schema change).

**Field-resampling convention** (the source spec only defines
weight/steps/cardio; `validate_log_input` requires waist/neck/intake too,
so they need a documented convention of their own): weight uses
**median** (robust to a single day's water/sodium swing, per spec);
steps/cardio use **mean** (spec-specified); waist/neck/intake extend the
same mean convention, since they lack weight's volatility argument;
`intake_is_real` is **AND-reduced** across the week's member rows (a week
counts as real-intake only if every logged day's intake was real) — this
adherence-relevant rule isn't in the source spec and is this
implementation's own conservative-by-design choice.

**Weekly view of daily logs** (what the source doc specifies — needed by
`CompositionEngine`, which is inherently a weekly-cadence engine):

```
s_i = mean(s_i^(1), ..., s_i^(7))     # steps
a_i = mean(a_i^(1), ..., a_i^(7))     # cardio
W_i = median(w_i^(1), w_i^(2), ...)   # weight -- median, not a single value or a mean
```

`W_i` degrades gracefully to a plain value when only one weigh-in exists
for the week (median of one point) — an account logging once a week
through this path is indistinguishable from today's behavior.

**Daily view of a weekly log** (new, symmetric direction — for any future
per-day display, not needed by the engine itself): a weekly log at date
`t_i` is copy-pasted across every day since the previous log, not
recomputed or interpolated:

```
daily_view(d) = BodyLog_i.(weight, steps, cardio)   for all d in (t_{i-1}, t_i]
```

This mirrors a pattern the engine already has: `activity_model="constant"`
(Projection.py) holds steps constant going *forward* into forecast weeks
absent better data; this holds a weekly log's values constant *backward*
across the days it actually covers, absent daily data. Both are the same
"carry the last known value when granularity is coarser than the view"
idea, just applied in opposite time directions.

**Net effect**: an account's granularity choice per log only needs
recording once, at capture time — no migration, no forced rollup step,
and mixed history (some weeks daily, some weekly) resolves correctly
either way. `daily_view` is implemented and unit-tested but not yet wired
to an API route or UI, since nothing in the app has a per-day display
today — it's a ready-made building block for the still-unscheduled README
"Phase 2.1" automatic steps/cardio import idea. Optional, not required for
F1–F5/F7/F8: a per-day target-calorie figure combining that day's NEAT,
its cardio, the week's BMR, and the daily surplus/deficit share — noted by
the source doc as the natural foundation for that same automatic
steps/cardio import from Health Connect / Google Fit.

### F7 — Real increment and deviation analytics (done)

```
IncrReal_i  = W_i / W_{i-1} - 1
IncrReal_bar = mean_i(IncrReal_i)
Desv_i      = (rho - IncrReal_i) / rho
```

`IncrReal_i` is algebraically identical to the already-implemented
`weight_delta_pct` (`pct_i` in this doc, `CompositionResult.weight_delta_pct`)
— `W_i/W_{i-1} - 1 == (W_i - W_{i-1})/W_{i-1}`. F7 adds no new base
computation here, only two new aggregate/derived views over an existing
field: the running mean `IncrReal_bar`, and `Desv_i`, the fraction of the
weekly-rate target missed (`0` = on target; `>0` under-shot; `<0`
over-shot). Both are cheap to compute from data already persisted.

Implemented as a new pure module, `services/composition/IncrementAnalytics.py`
(`compute_increment_analytics`) — real (non-projected) rows only, skipping
the first real row (its `weight_delta_pct` is the base-case `0.0`, not a
genuine week-over-week measurement). `IncrReal_bar` is an *expanding* mean up
to and including each row, not a fixed window. `rho` is the account's active
`GoalPlan.weekly_rate` (the same single value `Wobj_i` already uses across
the whole series, historized goal changes notwithstanding); `Desv_i` is
`None` when `rho == 0`. Exposed via `GET /api/metrics/increment-analytics`.

### F8 — Calibration constants (summary) (done)

New or promoted per-user-overridable constants, all defaulting to values
that reproduce today's Danel behavior exactly:

| Constant | Symbol | New default | Danel-equivalent today |
| --- | --- | --- | --- |
| RFM weight | `w_rfm` | `0.50` | `BF_WEIGHT_RFM`, currently a module-wide fixed constant, not per-user |
| Navy weight | `w_navy` | `0.25` | `BF_WEIGHT_NAVY`, ditto |
| Deurenberg weight | `w_deur` | `0.25` | `BF_WEIGHT_DEURENBERG`, ditto |
| Fat offset | `delta` | `0.0` | (none — new) |
| FFMI coefficient | `ffmi_coef` | `6.3` | hardcoded literal in `Anthropometry.py` |
| Lean-tissue energy density | `k_L` | `2100 kcal/kg` | (none — new, only used by F5) |
| Fat-mass energy density | `k_G` | `7700 kcal/kg` | `KCAL_PER_KG_FAT`, unchanged |
| Fat ratio ideal ceiling | `fat_ratio_ideal` | `0.25` | (none — new, only used by F3) |
| Reconciliation error threshold | `reconciliation_error_threshold_kcal` | `300 kcal/day` | (none — new, Phase 3.2, drives the "recalibrate" alert) |
| TEF | `tef` | `0.10` | `TEF`, unchanged value **and** unchanged application (divisor, `/(1-TEF)`) — see "Formula reconciliation" above |

`w_rfm + w_navy + w_deur` must sum to `1.0` (within tolerance) when
overridden. Sergio's own account would override `delta=0.02`,
`ffmi_coef=6.1`, keeping the default `0.50/0.25/0.25` weights — his
document doesn't actually change them, but the mechanism now exists for
an account that needs to. Every other account (including Danel's) keeps
the table above's defaults untouched.

### F9 — TEF by macronutrients (done, Phase 3.4)

Source: `docs/JustFitting_TEF_Macronutrientes.pdf` (v1.0, 2026-07-02) — a
separate document from the eight-capability Oleada 2 spec above, but
squarely an extension of it: it refines F4's flat-10% TEF into a value
computed from what was actually eaten, and it **needs F6's daily
granularity** to exist first (it reads grams of carbs/fat/protein per
day, so a week logged only at weekly granularity has nothing to compute
it from — see the degradation rule below).

**Daily TEF**, from a day's carbs `C_d`, fat `G_d`, protein `P_d` (all
grams):

```
TEF_d = kappa_C * C_d + kappa_G * G_d + kappa_P * P_d
kappa_C = 0.300, kappa_G = 0.135, kappa_P = 1.000    # kcal per gram
```

Each `kappa_m` decomposes as `e_m * tau_m` — energy density (kcal/g, the
standard Atwater values `4/9/4` for carbs/fat/protein) times that
macro's characteristic thermic fraction (`7.5%` / `1.5%` / `25%`).
Protein dominates TEF despite carbs and protein sharing the same energy
density, because protein's thermic fraction is over 3x carbs' and 16x
fat's — this is *why* a high-protein bulk has a materially higher TEF
than the flat 10% assumes, which is the whole motivation for this
feature. Expose both representations as overridable: `kappa_C/G/P`
directly, or the underlying `e_m`/`tau_m` pairs for someone who wants to
reason in "fraction of intake," per the source doc's own suggestion.

**Weekly TEF** — the mean of the week's daily values:

```
TEF_i = mean_d(TEF_d), d = 1..7
```

Verified against the source doc's worked week: Monday's `TEF_d =
0.300*233.9 + 0.135*90.6 + 1.000*198.4 = 70.17 + 12.23 + 198.40 = 280.80`
kcal, and the 7-day mean across the doc's full worked week comes to
`291.75` kcal — both reproduced exactly by hand.

**Replaces the flat estimate additively, not as a percentage**, once
macros are logged for the week:

```
TDEE_i      = BMR_i + NEAT_i + EAT_i + TEF_i
TargetCal_i = BMR_i + NEAT_i + EAT_i + TEF_i - DailyDeficit_i     # DailyDeficit_i as in F1 (negative => surplus)
```

This is the resolution the "Formula reconciliation" section above
anticipates: `TEF_i` here is an actually-computed kcal figure, not a
percentage of anything, so it's simply added — no divisor, no
multiplier, no algebraic derivation needed, because the 10%-of-TDEE
*approximation* that derivation justified is exactly what this feature
replaces once real macro data exists. The **daily** target-calorie figure
mirrors this with that day's own activity and TEF:

```
Objetivo_d = BMR_i + NEAT_d + Cardio_d + TEF_d + Superavit_dia_i     # NEAT_d = 0.5 * W_i * (Pasos_d / 1000)
```

**Graceful degradation** (`tef_mode = "flat" | "macros"`): a week with no
macros logged falls back to the existing flat/divisor formula
automatically, regardless of the account's preferred mode — F9 is
additive, never blocking, exactly like F6's daily/weekly coexistence it
depends on. **`tef_mode` is account-level only (`EngineConstants`/
`EngineSettings`, historized like every other calibration field), not a
per-request query-param override** — the source doc's own wording
suggested one, but the same reasoning `composition_spec.md`'s F4 section
gives for `bmr_model` applies here too: which TEF formula applies changes
every metrics computation for an account (`CompositionEngine.compute_row`,
cached per `(log_id, ENGINE_VERSION)`), not just an ephemeral forecast, so
it belongs on the same historized settings object as `bmr_model`, not a
request-scoped parameter.

**Implementation note**: `CompositionResult` gained two new fields,
`tef_kcal` (the actual kcal figure this row used, whichever formula
applied) and `tef_mode` (`"flat"` or `"macros"`, which one actually
applied to *this* row — independent of the account's `tef_mode` setting,
since a `"macros"`-mode week with nothing logged still falls back to
`"flat"`). Because this changes both the compute-order chain (the TDEE/
target-calories formula genuinely branches, not just a read-side view
like `GainQuality`/`EnergyReconciliation`) and `CompositionResult`'s own
shape, `CompositionEngine.ENGINE_VERSION` bumped `1 -> 2` — the first
version bump since the engine shipped — and `metrics_snapshots` gained
matching `tef_kcal`/`tef_mode` columns (migration 18). Every log with
`carbs_g`/`fat_g`/`protein_g` all unset (every log before this phase, and
every log at any granularity that simply doesn't log macros) computes
byte-for-byte identically to `ENGINE_VERSION=1`; the version bump exists
only so historical snapshots stay reproducible under the new fields'
presence, not because any existing formula's *output* changed.
`GET /api/metrics/tef` (`Tef.compute_tef_breakdown`, a read-side view
reusing each row's already-computed `bmr`/`neat`) breaks a week down by
macro and reports both the flat estimate and the macro figure side by
side for comparison, regardless of which one the account's `tef_mode`
actually applied that week.

**Macro fields live on `BodyLog` itself** (migration 16: `carbs_g`,
`fat_g`, `protein_g`, all nullable `REAL`), exactly as F6 anticipated —
no new table. They're logged **together or not at all**: `carbs_g`/
`fat_g`/`protein_g` must be all-`None` or all-set
(`CompositionEngine.validate_log_input` rejects a partial trio), since
there's no principled way to compute a macro-based TEF from only one or
two of the three. `LogResampler.resample_to_weekly` extends its existing
mean-of-logged-days convention to the three macro fields — averaging
whichever days in a daily-logged week actually have macros (minimum 1),
`None` if none do — which resolves the "partial week" open decision
below exactly as recommended, and works because TEF is linear in each
macro (the mean of daily TEF values equals the TEF of the mean macros, so
no special-casing is needed in `CompositionEngine` itself).

**A numeric inconsistency in the source doc, flagged rather than
silently reproduced**: its own worked TDEE integration example states
`BMR=1892.5, NEAT=159.4, EAT=478.6, TEF=288.3` summing to `TDEE=2854.8`.
Adding the four stated figures gives `2818.8`, not `2854.8` — a 36 kcal
(~1.3%) gap that doesn't reconcile as printed, most likely because the
displayed component values were rounded from higher-precision
intermediates that the displayed total was computed from directly. The
additive formula above is authoritative; don't treat `2854.8` itself as a
value to reproduce in tests.

**Open decision, resolved**: how to handle a week with some but not all 7
days logged. The source doc's own "Supuestos y limitaciones" raises this
without deciding it ("promediar solo los días registrados o exigir la
semana completa"). Resolved per the recommendation above: `LogResampler`
averages whatever days have macros logged (minimum 1), rather than
requiring a complete week — matching how `median(w^(1), ...)` in F6
already degrades gracefully with partial data.

New constants (extends F8's table, same per-account-overridable,
historized mechanism — field names below are the actual
`EngineConstants`/`EngineSettings` names, spelled out rather than the
source doc's `kappa_C`/`kappa_G`/`kappa_P` shorthand):

| Constant | Field name | Default | Notes |
| --- | --- | --- | --- |
| Carb TEF coefficient | `kappa_carbs` | `0.300 kcal/g` | `= e_carb (4) * tau_carb (7.5%)` |
| Fat TEF coefficient | `kappa_fat` | `0.135 kcal/g` | `= e_fat (9) * tau_fat (1.5%)` |
| Protein TEF coefficient | `kappa_protein` | `1.000 kcal/g` | `= e_protein (4) * tau_protein (25%)` |
| TEF mode | `tef_mode` | `"flat"` | `"flat"` (today's divisor formula, unchanged default) or `"macros"` (this section); falls back to `"flat"` per-week if macros aren't logged that week regardless of setting; account-level only, not per-request (see above) |
| Macro/intake mismatch threshold | `macro_kcal_mismatch_pct` | `0.15` (15%) | drives the `macro_kcal_mismatch` alert below; the source doc raises the coherence check without proposing a number, so this default is this implementation's own reasoned choice |

Other assumptions from the source doc, carried through unchanged: the
coefficients are literature averages that vary by individual, hence
overridable; Atwater densities don't account for alcohol or fiber
(unscheduled — could be added as further macro coefficients later).
The soft, non-blocking coherence check between declared `kcal` and
`4*carbs_g + 9*fat_g + 4*protein_g` the source doc calls for is
implemented as a new `macro_kcal_mismatch` detector in
`services/composition/Alerts.py`, flagging (never blocking) a week whose
relative gap exceeds `macro_kcal_mismatch_pct` — same flag-not-block
pattern as `IMPLAUSIBLE_WEEKLY_CHANGE_PCT`. The **daily** target-calorie
figure (`Objetivo_d` above) is not implemented — like `LogResampler.
daily_view` itself, nothing in the app has a per-day display yet, so
there's nowhere to show it; the weekly figures above are what's exposed.

### Macro targets by body mass — an extension beyond F9, not in either source doc

Evidence-based per-kg-bodyweight protein/fat targets, with carbs as the
remainder of calories once protein/fat's kcal share is subtracted —
requested as a follow-on to F9, not part of either the Oleada 2 or TEF
source PDFs. Commonly-cited sports-nutrition ranges:

| Macro | Cut | Bulk |
| --- | --- | --- |
| Protein | 1.6–2.2 g/kg | 1.5–2.0 g/kg |
| Fat | 0.5–0.8 g/kg | 0.7–1.0 g/kg |
| Carbs | remainder of calories | remainder of calories |

```
ProteinTarget_i^g    = protein_target_g_per_kg * W_i
FatTarget_i^g        = fat_target_g_per_kg * W_i
ProteinTarget_i^kcal = ProteinTarget_i^g * 4        # Atwater, ATWATER_PROTEIN_KCAL_PER_G
FatTarget_i^kcal     = FatTarget_i^g * 9            # Atwater, ATWATER_FAT_KCAL_PER_G
CarbsTarget_i^kcal   = max(0, TargetCal_i - ProteinTarget_i^kcal - FatTarget_i^kcal)
CarbsTarget_i^g      = CarbsTarget_i^kcal / 4        # Atwater, ATWATER_CARB_KCAL_PER_G
```

`protein_target_g_per_kg` (default `1.75`) and `fat_target_g_per_kg`
(default `0.70`) are new per-account-overridable `EngineConstants`/
`EngineSettings` fields — a single mid-point inside both the cut and
bulk ranges above, meant to be tuned per account within whichever range
applies; there is deliberately no `carbs_target_g_per_kg`, since carbs
are always the remainder, never an independently-set target, mirroring
how the source doc itself treats carbs. Implemented as a new pure
read-side module, `services/composition/MacroTargets.py`
(`compute_macro_targets`) — like `Tef.compute_tef_breakdown`, it reuses
each row's already-computed `target_calories` and needs no
`ENGINE_VERSION` bump. Exposed via `GET /api/metrics/macro-targets`,
reporting both the target split and (when this week's macros are
logged) the actual logged split for comparison.

Two new alerts extend `services/composition/Alerts.py`:
`protein_target_deviation` and `fat_target_deviation`, each flagging
(never blocking) a week whose logged protein/fat grams diverge from
their per-kg target by more than `macro_target_deviation_pct` (new
`EngineConstants`/`EngineSettings` field, default `0.20`, i.e. 20%) —
only fires on a week with macros actually logged; carbs (a derived
remainder, not an independent target) are never checked. The Dashboard
gained a stacked-bar chart (`drawMacroSplitBars`, a new `charts.js`
primitive) comparing the target split against the actual split in kcal,
per the project's dataviz guidance (a stacked bar is the recommended
form for part-to-whole comparison, in preference to a pie/donut chart).

## Health disclaimer

These are population-level estimates (RFM, US Navy method, Deurenberg),
not clinical measurements. JustFitting does not provide medical or
nutrition prescriptions — see the disclaimer in the client footer.
