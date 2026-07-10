# Import file format (JSON / CSV)

`POST /api/users/me/import` reads two top-level keys, both optional and
independent of each other:

```json
{
  "logs": [ { "...": "row" } ],
  "body_measurements": [ { "...": "row" } ]
}
```

The CSV path (`csvImport.js`, which turns a `.csv` file into `{"logs":
[...]}` before calling the same route) only ever produces the `logs`
key — there's no CSV import for `body_measurements` (see that section
below for why, and how a pre-Phase-9 CSV with perimeter columns still
works).

Everything else `GET /api/users/me/export` produces — `profile`,
`goal_history`, `audit_log`, and every Wave 2 read-side section
(`gain_quality`, `energy_balance`, `tef`, etc.) — is informational only
and silently ignored on import; a hand-written file can omit all of it
and just supply `{"logs": [...]}`. Profile and goal setup always happen
through registration/the Plan tab, never through import.

## `logs`

Each entry is one `BodyLog` row, validated by the same
`validate_log_input` (`server/src/services/composition/CompositionEngine.py`)
every manual wizard save goes through:

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `date` | `"YYYY-MM-DD"` | yes | Must be unique per account — a date colliding with an existing log is skipped with reason `"duplicate date"`, the rest of the file still imports. |
| `weight_kg` | number > 0 | no* | |
| `intake_kcal` | number > 0 | no* | |
| `steps` | number > 0 | no* | |
| `intake_is_real` | boolean | no (default `true`) | `false` marks intake as assumed/estimated rather than actually logged — affects the Adherence figure, not the engine's own math. |
| `cardio_kcal` | number ≥ 0 | no (default `0`) | Phase 3.1's EAT term. |
| `granularity` | `"daily"` \| `"weekly"` | no (default `"weekly"`) | `"daily"` rows in the same ISO week get resampled together (`LogResampler`, Phase 3.3). |
| `carbs_g`, `fat_g`, `protein_g` | number ≥ 0 | no | All three or none — a partial trio is rejected (whole row skipped). Omit all three (or `null`) for the flat-TEF fallback. |
| `source` | — | ignored | Always forced to `"real"` regardless of what's supplied — `"projected"` rows only ever come from the engine's own forecast, never a hand-written import. |
| `waist_cm`, `neck_cm` | number > 0 | no, backward-compat only | **Phase 9.1: no longer a `body_logs` field.** A pre-Phase-9 export (or any file written against the old format) can still carry these inline on a log entry — instead of being dropped, they're synthesized into a `body_measurements` row at that same log's date (see below), so restoring an old backup doesn't silently lose historical perimeter readings. A *new* export never emits them here; use the `body_measurements` array instead. |

\* Since Phase 7.4 (partial logs), the core fields are individually
optional — a row missing some of them imports as a genuinely partial row
(same as a manual partial save or a sync writing only steps/nutrition),
not rejected. A row is only useful for computation once weight/intake/steps
are present *and* a `body_measurements` row resolves waist/neck for that
date (Phase 9.1's "static until next update" rule), whether from one
import row or filled in later by an edit.

A row failing `validate_log_input` (e.g. a non-positive value) is skipped
with a reported reason (`skipped: [{row, reason}]` in the response) —
never a partial save of an *invalid* row. The inline `waist_cm`/`neck_cm`
backward-compat synthesis is best-effort and silent: it never fails the
log import itself, and does nothing if a `body_measurements` row already
exists at that date.

Example — two weekly rows plus one daily row with macros:

```json
{
  "logs": [
    {
      "date": "2026-01-05",
      "weight_kg": 91.4,
      "intake_kcal": 2300,
      "steps": 6200
    },
    {
      "date": "2026-01-12",
      "weight_kg": 90.9,
      "intake_kcal": 2250,
      "steps": 6400,
      "cardio_kcal": 150,
      "intake_is_real": true
    },
    {
      "date": "2026-01-13",
      "weight_kg": 90.8,
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

## `body_measurements`

Each entry is one sporadic perimeter reading (Phase 9.1/9.3, see README),
validated by `BodyMeasurementManager`'s own checks (positive values,
`waist_cm` strictly greater than `neck_cm` when both are present):

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `date` | `"YYYY-MM-DD"` | yes | Must be unique per account — a date colliding with an existing measurement is skipped with reason `"duplicate date"`. |
| `waist_cm`, `neck_cm` | number > 0 | no | The only two fields `CompositionEngine` ever reads. |
| `shoulder_cm`, `chest_cm`, `hips_cm`, `biceps_r_cm`, `biceps_l_cm`, `thigh_r_cm`, `thigh_l_cm`, `calf_r_cm`, `calf_l_cm` | number > 0 | no | Phase 9.3's record-only measurements — never read by the engine, purely a Body-view history entry. Always optional on import, so a pre-Phase-9.3 export (which won't have them at all) still imports cleanly. |

```json
{
  "body_measurements": [
    { "date": "2026-01-05", "waist_cm": 89.0, "neck_cm": 37.5 },
    {
      "date": "2026-03-01",
      "waist_cm": 85.0,
      "neck_cm": 37.0,
      "chest_cm": 105.0,
      "hips_cm": 100.0
    }
  ]
}
```

`GET /api/users/me/export`'s own output is always a valid import file
(for the same account, or a different one — the only per-account
constraint is the date-collision rules above): the fastest way to see the
exact shape a real, fully-populated account produces is exporting one and
reading its `logs`/`body_measurements` arrays.

## CSV

`logs` columns: `date,weight_kg,intake_kcal,steps,intake_is_real,
cardio_kcal,granularity,carbs_g,fat_g,protein_g` — header row required,
columns may appear in any order. `intake_is_real` accepts
`true`/`false`/`1`/`0`/`yes`/`no` (case-insensitive); a blank cell means
"not supplied," which for an optional field falls back to its default and
for a required field surfaces the same missing-field skip reason as JSON.
`source` is deliberately not a documented column — if present it's
carried through but ignored, forced to `"real"` either way. `waist_cm`/
`neck_cm` are still accepted as columns too (the same backward-compat
synthesis the JSON path uses applies here, since CSV rows go through the
exact same server-side import route) — a template written against the old
format still imports cleanly, including its perimeter columns.

There's no CSV import path for `body_measurements` specifically — the
Account view's Import control only ever produces `{"logs": [...]}` from a
`.csv` file (`csvImport.js`). Bulk-importing standalone measurement
history (independent of a log row) needs the JSON `body_measurements`
array above; this is a deliberate scope decision (record-only, low
volume, JSON already covers it) rather than an oversight.

A downloadable template (header row only) is linked next to the Import
control in the Account view:
`client/src/webapp/static/justfitting-import-template.csv`.
