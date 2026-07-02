"""Named constants for the body-composition engine (the "Danel" model).

Keep every magic number used by the engine here so routes and services never
inline them (see docs/composition_spec.md, section on guardrails).
"""

#: Thermic effect of food, applied as a divisor on (BMR + NEAT).
TEF = 0.10

#: Approximate kcal stored per kg of body fat, used to convert a weekly
#: weight-loss target into a caloric deficit.
KCAL_PER_KG_FAT = 7700.0

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
