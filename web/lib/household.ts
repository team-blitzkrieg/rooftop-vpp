import { isStale, type ForecastRow } from "@/lib/forecast";

/** Seeded stand-in for a Pi. Readings for this site are SIMULATED. */
export const DEMO_SIM_SITE = "demo-sim";

export type SiteDetail = {
  site_id: string;
  name: string | null;
  timezone: string;
  system_kw: number | null;
};

export type SourceKind = "measured" | "estimated" | "simulated" | "other";

export type SourceBadge = {
  kind: SourceKind;
  text: string;
};

export type Quantity = {
  value: number | null;
  source: SourceBadge | null;
};

export type ApplianceWindow = {
  label: string;
  source: SourceBadge;
  issuedAt: string;
};

export type HouseholdSnapshot = {
  mode: "live" | "offline";
  simulated: boolean;
  issuedAt: string | null;
  bannerTitle: string | null;
  bannerBody: string | null;
  solar: Quantity;
  home: Quantity;
  /** Positive net is import (demand above PV). */
  importing: Quantity;
  exporting: Quantity;
  selfPoweredPct: number | null;
  nonFossil: null;
  generatedKwh: Quantity;
  usedKwh: Quantity;
  exportedKwh: Quantity;
  importedKwh: Quantity;
  window: ApplianceWindow | null;
};

const EMPTY_QTY: Quantity = { value: null, source: null };

export function sourceBadge(row: Pick<ForecastRow, "data_label" | "is_simulated">): SourceBadge {
  const label = (row.data_label || "").trim();
  const upper = label.toUpperCase();
  if (row.is_simulated || upper === "SIMULATED") return { kind: "simulated", text: "Simulated" };
  if (upper === "ESTIMATED" || upper === "ESTIMATE") return { kind: "estimated", text: "Estimated" };
  if (upper === "MEASURED") return { kind: "measured", text: "Measured" };
  if (label) return { kind: "other", text: label };
  return { kind: "other", text: "Not available" };
}

function combine(rows: ForecastRow[]): SourceBadge | null {
  if (rows.length === 0) return null;
  const badges = rows.map(sourceBadge);
  if (badges.some((badge) => badge.kind === "simulated")) return { kind: "simulated", text: "Simulated" };
  if (badges.every((badge) => badge.kind === "measured")) return { kind: "measured", text: "Measured" };
  if (badges.every((badge) => badge.kind === "estimated")) return { kind: "estimated", text: "Estimated" };
  if (badges.every((badge) => badge.kind === "measured" || badge.kind === "estimated")) {
    return { kind: "estimated", text: "Estimated" };
  }
  return badges[0];
}

type Parts = {
  key: string;
  day: string;
  clock: string;
  dayLabel: string;
};

export function zonedParts(iso: string, timeZone: string): Parts {
  const list = new Intl.DateTimeFormat("en-GB", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(new Date(iso));
  const get = (type: string) => list.find((part) => part.type === type)?.value ?? "";
  const dayLabel = new Intl.DateTimeFormat("en-GB", {
    timeZone,
    day: "numeric",
    month: "short",
  }).format(new Date(iso));
  return {
    key: `${get("year")}-${get("month")}-${get("day")}-${get("hour")}`,
    day: `${get("year")}-${get("month")}-${get("day")}`,
    clock: `${get("hour")}:${get("minute")}`,
    dayLabel,
  };
}

function byTarget(rows: ForecastRow[], target: string): ForecastRow[] {
  return rows
    .filter((row) => row.target === target && Number.isFinite(Number(row.value_kw)))
    .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());
}

function atHour(rows: ForecastRow[], key: string, timeZone: string): ForecastRow | null {
  return rows.find((row) => zonedParts(row.timestamp, timeZone).key === key) ?? null;
}

function quantity(row: ForecastRow | null): Quantity {
  if (!row) return EMPTY_QTY;
  return { value: Number(row.value_kw), source: sourceBadge(row) };
}

function sumRows(rows: ForecastRow[]): Quantity {
  if (rows.length === 0) return EMPTY_QTY;
  const total = rows.reduce((sum, row) => sum + Number(row.value_kw), 0);
  return { value: total, source: combine(rows) };
}

function flowForHour(pv: ForecastRow | null, demand: ForecastRow | null, net: ForecastRow | null): {
  importing: Quantity;
  exporting: Quantity;
} {
  let netKw: number | null = null;
  let source: SourceBadge | null = null;
  if (net) {
    netKw = Number(net.value_kw);
    source = sourceBadge(net);
  } else if (pv && demand) {
    netKw = Number(demand.value_kw) - Number(pv.value_kw);
    source = combine([pv, demand]);
  }
  if (netKw === null || source === null) {
    return { importing: EMPTY_QTY, exporting: EMPTY_QTY };
  }
  return {
    importing: { value: Math.max(netKw, 0), source },
    exporting: { value: Math.max(-netKw, 0), source },
  };
}

function dayRows(rows: ForecastRow[], day: string, timeZone: string): ForecastRow[] {
  return rows.filter((row) => zonedParts(row.timestamp, timeZone).day === day);
}

function bestPvWindow(pvRows: ForecastRow[], timeZone: string): { start: string; end: string; rows: ForecastRow[] } | null {
  let best: { start: string; end: string; rows: ForecastRow[]; sum: number } | null = null;
  for (let index = 0; index <= pvRows.length - 3; index += 1) {
    const block = pvRows.slice(index, index + 3);
    const times = block.map((row) => new Date(row.timestamp).getTime());
    const stepA = times[1] - times[0];
    const stepB = times[2] - times[1];
    const hour = 60 * 60 * 1000;
    if (stepA < hour * 0.8 || stepA > hour * 1.2 || stepB < hour * 0.8 || stepB > hour * 1.2) continue;
    const sum = block.reduce((total, row) => total + Number(row.value_kw), 0);
    if (best && sum <= best.sum) continue;
    best = {
      start: block[0].timestamp,
      end: new Date(times[2] + hour).toISOString(),
      rows: block,
      sum,
    };
  }
  if (!best) return null;
  return { start: best.start, end: best.end, rows: best.rows };
}

export function formatWindow(start: string, end: string, timeZone: string): string {
  const from = zonedParts(start, timeZone);
  const to = zonedParts(end, timeZone);
  if (from.day === to.day) return `${from.clock} – ${to.clock}`;
  return `${from.dayLabel} ${from.clock} – ${to.dayLabel} ${to.clock}`;
}

export function formatPower(value: number | null, unit: "kW" | "kWh"): string {
  if (value === null || !Number.isFinite(value)) return "—";
  const rounded = Math.round(value * 10) / 10;
  const normal = Object.is(rounded, -0) ? 0 : rounded;
  const text = Number.isInteger(normal) ? String(normal) : normal.toFixed(1);
  return `${text} ${unit}`;
}

export function formatSystemKw(value: number | null): string | null {
  if (value === null || !Number.isFinite(Number(value))) return null;
  return formatPower(Number(value), "kW");
}

export function formatUpdated(iso: string | null, now = Date.now()): string {
  if (!iso) return "No forecast issued";
  const mins = Math.round((now - new Date(iso).getTime()) / 60000);
  if (!Number.isFinite(mins)) return "No forecast issued";
  if (mins < 1) return "Updated just now";
  if (mins < 60) return `Updated ${mins} min ago`;
  const hours = Math.round(mins / 60);
  if (hours < 36) return `Updated ${hours} h ago`;
  return `Updated ${new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).format(new Date(iso))}`;
}

export function buildSnapshot(
  rows: ForecastRow[],
  timeZone: string,
  now = new Date(),
): HouseholdSnapshot {
  const pvRows = byTarget(rows, "pv");
  const demandRows = byTarget(rows, "demand");
  const netRows = byTarget(rows, "net");
  const issuedAt = rows.find((row) => row.issued_at)?.issued_at ?? null;
  const nowKey = zonedParts(now.toISOString(), timeZone).key;
  const today = zonedParts(now.toISOString(), timeZone).day;

  const livePv = atHour(pvRows, nowKey, timeZone);
  const liveDemand = atHour(demandRows, nowKey, timeZone);
  const liveNet = atHour(netRows, nowKey, timeZone);
  const hasNow = Boolean(livePv || liveDemand || liveNet);
  const stale = issuedAt ? isStale(issuedAt, now.getTime()) : true;
  const live = hasNow && !stale && rows.length > 0;

  const chosenTime = hasNow
    ? now.toISOString()
    : latestAtOrBefore(rows, now) ?? rows[0]?.timestamp ?? null;
  const chosenKey = chosenTime ? zonedParts(chosenTime, timeZone).key : "";
  const pv = hasNow ? livePv : atHour(pvRows, chosenKey, timeZone);
  const demand = hasNow ? liveDemand : atHour(demandRows, chosenKey, timeZone);
  const net = hasNow ? liveNet : atHour(netRows, chosenKey, timeZone);
  const flows = flowForHour(pv, demand, net);

  const pvToday = dayRows(pvRows, today, timeZone);
  const demandToday = dayRows(demandRows, today, timeZone);
  const netToday = dayRows(netRows, today, timeZone);
  const importedRows: ForecastRow[] = [];
  const exportedRows: ForecastRow[] = [];
  const hours = new Set<string>([
    ...pvToday.map((row) => zonedParts(row.timestamp, timeZone).key),
    ...demandToday.map((row) => zonedParts(row.timestamp, timeZone).key),
    ...netToday.map((row) => zonedParts(row.timestamp, timeZone).key),
  ]);
  for (const key of hours) {
    const hourPv = atHour(pvToday, key, timeZone);
    const hourDemand = atHour(demandToday, key, timeZone);
    const hourNet = atHour(netToday, key, timeZone);
    const hour = flowForHour(hourPv, hourDemand, hourNet);
    if (hour.importing.value !== null && hour.importing.source) {
      importedRows.push(fakeRow(hour.importing));
    }
    if (hour.exporting.value !== null && hour.exporting.source) {
      exportedRows.push(fakeRow(hour.exporting));
    }
  }

  const windowBlock = bestPvWindow(pvRows, timeZone);
  const window = windowBlock
    ? {
        label: formatWindow(windowBlock.start, windowBlock.end, timeZone),
        source: combine(windowBlock.rows) ?? { kind: "other" as const, text: "Not available" },
        issuedAt: windowBlock.rows[0]?.issued_at ?? issuedAt ?? "",
      }
    : null;

  let selfPoweredPct: number | null = null;
  if (pv && demand && Number(demand.value_kw) > 0) {
    selfPoweredPct = Math.min(100, Math.max(0, (Number(pv.value_kw) / Number(demand.value_kw)) * 100));
  }

  let bannerTitle: string | null = null;
  let bannerBody: string | null = null;
  if (rows.length === 0) {
    bannerTitle = "No forecast yet";
    bannerBody = "This home has no forecast rows. Nothing here is filled in until a forecast is issued.";
  } else if (!live) {
    bannerTitle = stale ? "Forecast is stale" : "No forecast for this hour";
    bannerBody = issuedAt
      ? `Showing the latest forecast, issued ${formatUpdated(issuedAt, now.getTime()).replace(/^Updated /, "")}. These are not live meter readings. The edge design keeps up to 7 days and uploads on reconnect. This app cannot see that buffer.`
      : "Showing the latest forecast. These are not live meter readings. The edge design keeps up to 7 days and uploads on reconnect. This app cannot see that buffer.";
  }

  return {
    mode: live ? "live" : "offline",
    simulated: rows.some((row) => sourceBadge(row).kind === "simulated"),
    issuedAt,
    bannerTitle,
    bannerBody,
    solar: quantity(pv),
    home: quantity(demand),
    importing: flows.importing,
    exporting: flows.exporting,
    selfPoweredPct,
    nonFossil: null,
    generatedKwh: sumRows(pvToday),
    usedKwh: sumRows(demandToday),
    exportedKwh: sumRows(exportedRows),
    importedKwh: sumRows(importedRows),
    window: rows.length === 0 ? null : window,
  };
}

function fakeRow(quantityValue: Quantity): ForecastRow {
  const source = quantityValue.source ?? { kind: "other", text: "Not available" };
  return {
    target: "net",
    timestamp: "",
    issued_at: "",
    value_kw: quantityValue.value ?? 0,
    baseline_kw: null,
    model_version: "",
    data_label:
      source.kind === "simulated"
        ? "SIMULATED"
        : source.kind === "measured"
          ? "MEASURED"
          : source.kind === "estimated"
            ? "ESTIMATED"
            : source.text,
    is_simulated: source.kind === "simulated",
  };
}

function latestAtOrBefore(rows: ForecastRow[], now: Date): string | null {
  const nowMs = now.getTime();
  let best: string | null = null;
  let bestMs = -Infinity;
  for (const row of rows) {
    const ms = new Date(row.timestamp).getTime();
    if (ms <= nowMs && ms > bestMs) {
      best = row.timestamp;
      bestMs = ms;
    }
  }
  if (best) return best;
  let earliest: string | null = null;
  let earliestMs = Infinity;
  for (const row of rows) {
    const ms = new Date(row.timestamp).getTime();
    if (ms < earliestMs) {
      earliest = row.timestamp;
      earliestMs = ms;
    }
  }
  return earliest;
}

export function dominantGrid(snapshot: Pick<HouseholdSnapshot, "importing" | "exporting">): {
  value: number | null;
  caption: string;
  source: SourceBadge | null;
} {
  const imp = snapshot.importing.value;
  const exp = snapshot.exporting.value;
  if (imp === null && exp === null) return { value: null, caption: "No forecast", source: null };
  if ((exp ?? 0) > (imp ?? 0)) {
    return { value: exp, caption: "Exporting", source: snapshot.exporting.source };
  }
  if ((imp ?? 0) > (exp ?? 0)) {
    return { value: imp, caption: "Importing", source: snapshot.importing.source };
  }
  return { value: exp ?? imp, caption: "Balanced", source: snapshot.exporting.source ?? snapshot.importing.source };
}
