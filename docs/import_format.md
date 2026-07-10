# Import file format (JSON / CSV)

`POST /api/users/me/import` and the CSV path (`csvImport.js`, which
turns a `.csv` file into the same shape before calling the same route)
both only ever read one top-level key:

```json
{ "logs": [ { "...": "row" }, { "...": "row" } ] }
```

Everything else `GET /api/users/me/export` produces — `profile`,
`goal_history`, `audit_log`, and every Wave 2 read-side section
(`gain_quality`, `energy_balance`, `tef`, etc.) — is informational only
and silently ignored on import; a hand-written file can omit all of it
and just supply `{"logs": [...]}`. Profile and goal setup always happen
through registration/the Plan tab, never through import.

Each entry in `logs` is one `BodyLog` row, validated by the same
`validate_log_input` (`server/src/services/composition/CompositionEngine.py`)
every manual wizard save goes through:

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `date` | `"YYYY-MM-DD"` | yes | Must be unique per account — a date colliding with an existing log is skipped with reason `"duplicate date"`, the rest of the file still imports. |
| `weight_kg` | number > 0 | no* | |
| `waist_cm` | number > 0 | no* | Must be strictly greater than `neck_cm` when both are present. |
| `neck_cm` | number > 0 | no* | |
| `intake_kcal` | number > 0 | no* | |
| `steps` | number > 0 | no* | |
| `intake_is_real` | boolean | no (default `true`) | `false` marks intake as assumed/estimated rather than actually logged — affects the Adherence figure, not the engine's own math. |
| `cardio_kcal` | number ≥ 0 | no (default `0`) | Phase 3.1's EAT term. |
| `granularity` | `"daily"` \| `"weekly"` | no (default `"weekly"`) | `"daily"` rows in the same ISO week get resampled together (`LogResampler`, Phase 3.3). |
| `carbs_g`, `fat_g`, `protein_g` | number ≥ 0 | no | All three or none — a partial trio is rejected (whole row skipped). Omit all three (or `null`) for the flat-TEF fallback. |
| `source` | — | ignored | Always forced to `"real"` regardless of what's supplied — `"projected"` rows only ever come from the engine's own forecast, never a hand-written import. |

\* Since Phase 7.4 (partial logs), the five core fields are individually
optional — a row missing some of them imports as a genuinely partial row
(same as a manual partial save or a sync writing only steps/nutrition),
not rejected. A row is only useful for computation once all five are
present, whether from one import row or filled in later by an edit.

A row failing `validate_log_input` (e.g. `waist_cm <= neck_cm`, a
non-positive value) is skipped with a reported reason
(`skipped: [{row, reason}]` in the response) — never a partial save of an
*invalid* row.

Example — two weekly rows plus one daily row with macros:

```json
{
  "logs": [
    {
      "date": "2026-01-05",
      "weight_kg": 91.4,
      "waist_cm": 89.0,
      "neck_cm": 37.5,
      "intake_kcal": 2300,
      "steps": 6200
    },
    {
      "date": "2026-01-12",
      "weight_kg": 90.9,
      "waist_cm": 88.2,
      "neck_cm": 37.4,
      "intake_kcal": 2250,
      "steps": 6400,
      "cardio_kcal": 150,
      "intake_is_real": true
    },
    {
      "date": "2026-01-13",
      "weight_kg": 90.8,
      "waist_cm": 88.1,
      "neck_cm": 37.4,
      "intake_kcal": 2280,
      "steps": 7100,
      "granularity": "daily",
      "carbs_g": 250,
      "fat_g": 70,
      "protein_g": 160
    }
  ]
}
```

`GET /api/users/me/export`'s own output is always a valid import file
(for the same account, or a different one — the only per-account
constraint is the date-collision rule above): the fastest way to see the
exact shape a real, fully-populated account produces is exporting one
and reading its `logs` array.

## CSV

The same field set, as columns: `date,weight_kg,waist_cm,neck_cm,
intake_kcal,steps,intake_is_real,cardio_kcal,granularity,carbs_g,fat_g,
protein_g` — header row required, columns may appear in any order.
`intake_is_real` accepts `true`/`false`/`1`/`0`/`yes`/`no`
(case-insensitive); a blank cell means "not supplied," which for an
optional field falls back to its default and for a required field
surfaces the same missing-field skip reason as JSON. `source` is
deliberately not a documented column — if present it's carried through
but ignored, forced to `"real"` either way.

A downloadable template (header row only) is linked next to the Import
control in the Account view:
`client/src/webapp/static/justfitting-import-template.csv`.
