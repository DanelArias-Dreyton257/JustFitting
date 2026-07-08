"""Named constants for the body-composition engine (the "Demo_cut" model).

Keep every magic number used by the engine here so routes and services never
inline them (see docs/composition_spec.md, section on guardrails).
"""

#: Thermic effect of food, applied as a divisor on (BMR + NEAT).
TEF = 0.10

#: Approximate kcal stored per kg of body fat, used to convert a weekly
#: weight-loss target into a caloric deficit.
KCAL_PER_KG_FAT = 7700.0

#: NEAT is estimated as this fraction of (weight_kg * steps/1000).
NEAT_STEP_FACTOR = 0.5

#: A week-over-week weight swing beyond this fraction of body weight is
#: implausible for a single week and gets flagged (not blocked).
IMPLAUSIBLE_WEEKLY_CHANGE_PCT = 0.08

#: Weighted-mean coefficients for the headline body-fat percentage,
#: combining RFM, the US Navy method and the Deurenberg formula.
BF_WEIGHT_RFM = 0.50
BF_WEIGHT_NAVY = 0.25
BF_WEIGHT_DEURENBERG = 0.25

#: Reference height (m) FFMI is normalized against.
FFMI_HEIGHT_REF_M = 1.80

#: Average length of a calendar year in days, used for age calculation.
DAYS_PER_YEAR = 365.25

#: Days in a projection step (one logged week).
DAYS_PER_WEEK = 7

SEX_MALE = 1
SEX_FEMALE = 0

#: Phase 5.2 -- sane per-sex defaults for a brand-new account's goal plan,
#: used only when registration omits target_bf/weekly_rate. Every account
#: still always gets *a* goal plan (the engine has no "no goal" mode); this
#: just avoids asking for one at signup, deferring the real choice to the
#: Plan tab's preview/commit flow.
DEFAULT_TARGET_BF_MALE = 0.15
DEFAULT_TARGET_BF_FEMALE = 0.22
DEFAULT_WEEKLY_RATE = 0.0

#: Alerts & feedback thresholds (see services/composition/Alerts.py).
#: These, plus TEF/KCAL_PER_KG_FAT/NEAT_STEP_FACTOR above, are the module
#: defaults used when a user has no `EngineSettings` override (Phase 1.5,
#: see `services/composition/models.EngineConstants` and
#: `services/EngineSettingsManager.py`).

#: Consecutive real weeks with |dW| under this many kg counts as a plateau.
STAGNATION_WEEKS = 3
STAGNATION_THRESHOLD_KG = 0.15

#: Rolling window (real weeks) used to judge the lean-vs-total split of
#: recent weight change.
LEAN_LOSS_WINDOW_WEEKS = 4
#: Flag when lean mass makes up more than this share of a net weight loss
#: over the window.
MAX_LEAN_MASS_LOSS_SHARE = 0.35

#: |actual weight - weekly objective (Wobj)| beyond this many kg is a
#: significant deviation from the goal trajectory.
SIGNIFICANT_DEVIATION_KG = 1.0

#: Per-week decay factor for the "weighted_ols" projection trend model
#: (Phase 1.6, see services/composition/Projection.py) -- a point one week
#: older than the most recent one in the regression window is weighted by
#: this factor, two weeks older by its square, and so on.
WEIGHTED_TREND_DECAY = 0.85

#: Wave 2 (Phase 3) calibration constants -- see docs/composition_spec.md's
#: "Wave 2" section, F8. All default to values that reproduce today's
#: Demo_cut numbers exactly; every field below is promoted to a per-account
#: overridable `EngineConstants`/`EngineSettings` field (Phase 3), same
#: "no row = today's behavior" contract as every constant above.

#: Fat-percentage offset added to the weighted body-fat mean (`delta`).
BF_FAT_OFFSET = 0.0

#: FFMI adjustment coefficient -- promotes the literal `6.3` previously
#: hardcoded in Anthropometry.py to a named, overridable constant.
FFMI_COEF = 6.3

#: Lean-tissue energy density (kcal/kg), used by Phase 3.2's energy
#: reconciliation (F5) -- not consumed until then, but the constant/setting
#: ships now alongside the rest of F8's calibration surface.
LEAN_TISSUE_KCAL_PER_KG = 2100.0

#: Ideal ceiling on the fat share of a weight gain (Phase 3.1's gain-quality
#: panel, F3) -- a "clean" bulk keeps the fat share of the gain at or below
#: this fraction.
FAT_RATIO_IDEAL = 0.25

#: Recommended weekly bulk-rate range (Phase 3, F1) -- a bulk goal outside
#: this range is flagged (not blocked), mirroring
#: IMPLAUSIBLE_WEEKLY_CHANGE_PCT's flag-not-block pattern.
BULK_RATE_MIN = 0.0025
BULK_RATE_MAX = 0.005

#: Phase 3.2 (Wave 2, F5/F7) -- energy reconciliation & increment analytics.
#: See docs/composition_spec.md's "Wave 2" section, F5.

#: |ingested surplus - tissue surplus| (kcal/day) beyond this many kcal is
#: flagged (not blocked) as a "recalibrate" alert -- same flag-not-block
#: pattern as every other alert threshold above, and per-account
#: overridable via `EngineConstants.reconciliation_error_threshold_kcal`.
RECONCILIATION_ERROR_THRESHOLD_KCAL = 300.0

#: How many of the most recent computed weekly errors feed the rolling-mean
#: view `EnergyReconciliation.py` surfaces alongside the raw per-week error.
#: Not per-account overridable (like WEIGHTED_TREND_DECAY above) -- it's a
#: display smoothing window, not a physiological constant.
ENERGY_RECONCILIATION_WINDOW_WEEKS = 4

#: Phase 3.4 (Wave 2, F9) -- TEF computed directly from logged
#: carb/fat/protein grams instead of the flat 10% (`TEF` above) guess.
#: See docs/composition_spec.md's "Wave 2" section, F9.

#: kcal per gram of macro, each decomposed as energy density (kcal/g) times
#: that macro's characteristic thermic fraction: carbs 4 * 7.5%, fat 9 *
#: 1.5%, protein 4 * 25% -- protein dominates TEF despite sharing carbs'
#: energy density, since its thermic fraction is over 3x carbs' and 16x fat's.
KAPPA_CARBS = 0.300
KAPPA_FAT = 0.135
KAPPA_PROTEIN = 1.000

#: "flat" (today's divisor formula, unchanged default) or "macros" (F9,
#: additive) -- a week with no macros logged falls back to "flat"
#: automatically regardless of this setting (see CompositionEngine.compute_row).
TEF_MODE_DEFAULT = "flat"

#: Standard Atwater energy densities (kcal/g) -- fixed nutritional-science
#: conversion factors, not part of the per-account TEF calibration surface
#: above (`KAPPA_*`). Used only for the soft, non-blocking coherence check
#: between a week's declared intake_kcal and what its logged macros imply.
ATWATER_CARB_KCAL_PER_G = 4.0
ATWATER_FAT_KCAL_PER_G = 9.0
ATWATER_PROTEIN_KCAL_PER_G = 4.0

#: A week's logged intake vs. its macro-implied kcal (4*carbs + 9*fat +
#: 4*protein) differing by more than this relative share is flagged (not
#: blocked), mirroring IMPLAUSIBLE_WEEKLY_CHANGE_PCT's flag-not-block
#: pattern. The source doc raises this coherence check without proposing a
#: number; this default is this implementation's own reasoned choice.
MACRO_KCAL_MISMATCH_PCT = 0.15

#: Evidence-based per-kg-bodyweight macro targets -- an extension beyond the
#: F9 source doc, not scoped there. Protein and fat are set directly;
#: carbs are the "remainder of calories" once protein/fat's kcal share is
#: subtracted from target_calories, so there's no carbs-per-kg constant.
#: Sports-nutrition literature commonly cites 1.6-2.2 g/kg protein and
#: 0.5-0.8 g/kg fat for a cut, and 1.5-2.0 g/kg protein and 0.7-1.0 g/kg fat
#: for a bulk -- these defaults are a single mid-point inside both ranges,
#: meant to be tuned per account within whichever range applies.
PROTEIN_TARGET_G_PER_KG = 1.75
FAT_TARGET_G_PER_KG = 0.70

#: A week's logged protein/fat grams vs. its per-kg target differing by more
#: than this relative share is flagged (not blocked) -- own reasoned
#: default, same flag-not-block pattern as MACRO_KCAL_MISMATCH_PCT above.
MACRO_TARGET_DEVIATION_PCT = 0.20
