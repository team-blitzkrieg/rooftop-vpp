/** JSON contract for POST /api/ingest. The device token is a header, never a field. */

export const INGEST_LIMIT_PER_MINUTE = 30;
export const INGEST_MAX_READINGS = 48;

const LABELS = new Set(["MEASURED", "ESTIMATED", "SIMULATED"]);
const POWER_FIELDS = ["pv_kw", "consumption_kw", "import_kw", "export_kw"] as const;

export type IngestReading = {
  timestamp: string;
  pv_kw: number | null;
  consumption_kw: number | null;
  import_kw: number | null;
  export_kw: number | null;
  data_label: "MEASURED" | "ESTIMATED" | "SIMULATED";
  is_simulated: boolean;
};

export type IngestParse =
  | { ok: true; readings: IngestReading[] }
  | { ok: false; status: number; error: string };

export function rateDecision(hitsInLastMinute: number, limit = INGEST_LIMIT_PER_MINUTE): "ok" | "limited" {
  return hitsInLastMinute >= limit ? "limited" : "ok";
}

export function parseIngestBody(body: unknown): IngestParse {
  const list = Array.isArray(body)
    ? body
    : body && typeof body === "object" && Array.isArray((body as { readings?: unknown }).readings)
      ? (body as { readings: unknown[] }).readings
      : body && typeof body === "object"
        ? [body]
        : null;
  if (!list) return { ok: false, status: 422, error: "Send a reading object or { readings: [...] }." };
  if (list.length === 0) return { ok: false, status: 422, error: "readings is empty." };
  if (list.length > INGEST_MAX_READINGS) {
    return { ok: false, status: 422, error: `At most ${INGEST_MAX_READINGS} readings per request.` };
  }
  const readings: IngestReading[] = [];
  for (const item of list) {
    const parsed = oneReading(item);
    if ("error" in parsed) return { ok: false, status: 422, error: parsed.error };
    readings.push(parsed);
  }
  return { ok: true, readings };
}

function oneReading(item: unknown): IngestReading | { error: string } {
  if (!item || typeof item !== "object") return { error: "Each reading must be an object." };
  const row = item as Record<string, unknown>;
  if (typeof row.timestamp !== "string" || Number.isNaN(Date.parse(row.timestamp))) {
    return { error: "timestamp must be an ISO-8601 string." };
  }
  const powers: Record<(typeof POWER_FIELDS)[number], number | null> = {
    pv_kw: null,
    consumption_kw: null,
    import_kw: null,
    export_kw: null,
  };
  for (const field of POWER_FIELDS) {
    if (row[field] === undefined || row[field] === null) continue;
    if (typeof row[field] !== "number" || !Number.isFinite(row[field])) {
      return { error: `${field} must be a finite number or null.` };
    }
    if ((row[field] as number) < 0) return { error: `${field} cannot be negative.` };
    powers[field] = row[field] as number;
  }
  if (Object.values(powers).every((value) => value === null)) {
    return { error: "Send at least one of pv_kw, consumption_kw, import_kw, export_kw." };
  }
  const simulated = row.is_simulated === true;
  const label = row.data_label === undefined ? (simulated ? "SIMULATED" : "MEASURED") : row.data_label;
  if (typeof label !== "string" || !LABELS.has(label)) {
    return { error: "data_label must be MEASURED, ESTIMATED, or SIMULATED." };
  }
  if (simulated && label !== "SIMULATED") {
    return { error: "Simulated readings must use data_label SIMULATED." };
  }
  if (!simulated && label === "SIMULATED") {
    return { error: "data_label SIMULATED requires is_simulated true." };
  }
  return {
    timestamp: new Date(row.timestamp).toISOString(),
    ...powers,
    data_label: label as IngestReading["data_label"],
    is_simulated: simulated,
  };
}
