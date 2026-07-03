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

## Health disclaimer

These are population-level estimates (RFM, US Navy method, Deurenberg),
not clinical measurements. JustFitting does not provide medical or
nutrition prescriptions — see the disclaimer in the client footer.
