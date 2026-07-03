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

### F1 — Surplus/bulk mode

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

### F2 — Cardio (EAT) input

Just a new field on the weekly record, `cardio_kcal` (`a_i`); see F4 for
where it enters the energy chain, and F6 for its daily-aggregated form.

### F3 — Gain quality (lean/fat partition of the *change*)

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

### F4 — Second BMR model (Mifflin–St Jeor)

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

### F5 — Energy reconciliation ("Error")

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
a-posteriori validation, not a same-week metric. Recommend surfacing a
rolling mean of `Error_i` alongside the raw value (source doc's own
suggestion).

### F6 — Daily and weekly logs coexist; each view resamples the other

Revised design (beyond the source doc, which only specifies the
weekly-from-daily direction): rather than a separate `DailyEntry` table
that exists purely to feed a required weekly rollup, a log row carries a
`granularity = daily | weekly` tag, the same way it already carries
`source = real | projected` — one table, one new discriminator, not a new
entity. Every consumer resolves whichever granularity it needs from
whatever's actually stored, in both directions:

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
either way. Optional, not required for F1–F5/F7/F8: a per-day
target-calorie figure combining that day's NEAT, its cardio, the week's
BMR, and the daily surplus/deficit share — noted by the source doc as the
natural foundation for the already-recorded (README "Phase 2.1",
unscheduled) automatic steps/cardio import from Health Connect / Google
Fit.

### F7 — Real increment and deviation analytics

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

### F8 — Calibration constants (summary)

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
| TEF | `tef` | `0.10` | `TEF`, unchanged value **and** unchanged application (divisor, `/(1-TEF)`) — see "Formula reconciliation" above |

`w_rfm + w_navy + w_deur` must sum to `1.0` (within tolerance) when
overridden. Sergio's own account would override `delta=0.02`,
`ffmi_coef=6.1`, keeping the default `0.50/0.25/0.25` weights — his
document doesn't actually change them, but the mechanism now exists for
an account that needs to. Every other account (including Danel's) keeps
the table above's defaults untouched.

### F9 — TEF by macronutrients (a ninth capability, from a third source doc)

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

**Graceful degradation** (`tef_mode = flat | macros`, account setting +
optional per-request override): a week with no macros logged falls back
to the existing flat/divisor formula automatically, regardless of the
account's preferred mode — F9 is additive, never blocking, exactly like
F6's daily/weekly coexistence it depends on.

**A numeric inconsistency in the source doc, flagged rather than
silently reproduced**: its own worked TDEE integration example states
`BMR=1892.5, NEAT=159.4, EAT=478.6, TEF=288.3` summing to `TDEE=2854.8`.
Adding the four stated figures gives `2818.8`, not `2854.8` — a 36 kcal
(~1.3%) gap that doesn't reconcile as printed, most likely because the
displayed component values were rounded from higher-precision
intermediates that the displayed total was computed from directly. The
additive formula above is authoritative; don't treat `2854.8` itself as a
value to reproduce in tests.

**Open decision, not resolved by the source doc**: how to handle a week
with some but not all 7 days logged. The doc's own "Supuestos y
limitaciones" raises this without deciding it ("promediar solo los días
registrados o exigir la semana completa"). Recommended, for consistency
with F6's own graceful-degradation philosophy: average whatever days
have macros logged (minimum 1), rather than requiring a complete week —
matching how `median(w^(1), ...)` in F6 already degrades gracefully with
partial data.

New constants (extends F8's table, same per-account-overridable,
historized mechanism):

| Constant | Symbol | Default | Notes |
| --- | --- | --- | --- |
| Carb TEF coefficient | `kappa_C` | `0.300 kcal/g` | `= e_carb (4) * tau_carb (7.5%)` |
| Fat TEF coefficient | `kappa_G` | `0.135 kcal/g` | `= e_fat (9) * tau_fat (1.5%)` |
| Protein TEF coefficient | `kappa_P` | `1.000 kcal/g` | `= e_protein (4) * tau_protein (25%)` |
| TEF mode | `tef_mode` | `"flat"` | `"flat"` (today's divisor formula, unchanged default) or `"macros"` (this section); falls back to `"flat"` per-week if macros aren't logged that week regardless of setting |

Other assumptions from the source doc, carried through unchanged: the
coefficients are literature averages that vary by individual, hence
overridable; Atwater densities don't account for alcohol or fiber
(unscheduled — could be added as further macro coefficients later); and
a soft, non-blocking coherence check between declared `kcal` and `4*C_d +
9*G_d + 4*P_d` is worth surfacing (flag, don't block, same pattern as
`IMPLAUSIBLE_WEEKLY_CHANGE_PCT`), not enforcing an exact match.

## Health disclaimer

These are population-level estimates (RFM, US Navy method, Deurenberg),
not clinical measurements. JustFitting does not provide medical or
nutrition prescriptions — see the disclaimer in the client footer.
