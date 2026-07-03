"""Named constants for the body-composition engine (the "Danel" model).

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
