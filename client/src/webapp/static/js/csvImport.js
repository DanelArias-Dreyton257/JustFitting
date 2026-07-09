// Turns a CSV file into the exact {logs: [...]} shape POST
// /api/users/me/import already accepts and validates (see README's Phase
// 7.2/7.1) -- CSV is a second on-ramp into the same hardened server-side
// pipeline the JSON import path uses, not a parallel one. No third-party
// CSV library: this project has never taken on a JS dependency (see
// charts.js's hand-rolled SVG); the parser below is a small RFC 4180-ish
// dialect (quoted fields, "" escapes a literal quote).

const REQUIRED_COLUMNS = [
  "date",
  "weight_kg",
  "waist_cm",
  "neck_cm",
  "intake_kcal",
  "steps",
];

const NUMERIC_COLUMNS = [
  "weight_kg",
  "waist_cm",
  "neck_cm",
  "intake_kcal",
  "steps",
  "cardio_kcal",
  "carbs_g",
  "fat_g",
  "protein_g",
];

function splitCsvLine(line) {
  const fields = [];
  let field = "";
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const char = line[i];
    if (inQuotes) {
      if (char === '"') {
        if (line[i + 1] === '"') {
          field += '"';
          i++;
        } else {
          inQuotes = false;
        }
      } else {
        field += char;
      }
    } else if (char === '"') {
      inQuotes = true;
    } else if (char === ",") {
      fields.push(field);
      field = "";
    } else {
      field += char;
    }
  }
  fields.push(field);
  return fields.map((value) => value.trim());
}

// Returns `undefined` (meaning "omit this field, let the server default
// apply") for blank/unrecognized values, rather than passing through a raw
// string -- Python's bool("false") is True, so leaving type coercion to the
// server for this field specifically would silently mark every row as
// real intake regardless of what the CSV says.
function parseBoolean(raw) {
  const value = raw.trim().toLowerCase();
  if (["true", "1", "yes"].includes(value)) return true;
  if (["false", "0", "no"].includes(value)) return false;
  return undefined;
}

// `undefined` for blank/unparseable, same "omit rather than send a bad
// value" reasoning as parseBoolean -- a required column left `undefined`
// surfaces as the same per-row "missing field" skip reason the JSON path
// already reports (Phase 7.1), instead of a client-side error aborting the
// whole file.
function parseNumber(raw) {
  const value = raw.trim();
  if (value === "") return undefined;
  const number = Number(value);
  return Number.isNaN(number) ? undefined : number;
}

export function parseCsvLogs(text) {
  const lines = text.split(/\r?\n/).filter((line) => line.trim() !== "");
  if (lines.length === 0) return { logs: [] };

  const header = splitCsvLine(lines[0]).map((name) => name.toLowerCase());
  const missing = REQUIRED_COLUMNS.filter((name) => !header.includes(name));
  if (missing.length > 0) {
    throw new Error(`CSV is missing required column(s): ${missing.join(", ")}`);
  }

  const logs = lines.slice(1).map((line) => {
    const fields = splitCsvLine(line);
    const row = {};
    header.forEach((name, index) => {
      const raw = fields[index] ?? "";
      if (name === "intake_is_real") {
        const parsed = parseBoolean(raw);
        if (parsed !== undefined) row[name] = parsed;
      } else if (NUMERIC_COLUMNS.includes(name)) {
        const parsed = parseNumber(raw);
        if (parsed !== undefined) row[name] = parsed;
      } else if (raw !== "") {
        // date, granularity, and anything else (e.g. a stray "source"
        // column -- always ignored server-side, see Phase 7.1) pass
        // through as plain strings.
        row[name] = raw;
      }
    });
    return row;
  });

  return { logs };
}
