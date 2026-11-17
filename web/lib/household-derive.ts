import type { ForecastRow } from "@/lib/forecast";
import { isStale } from "@/lib/forecast";
import type { Load } from "@/lib/demo-store";
import { loadEnergyKwh } from "@/lib/demo-store";
import { sourceBadge, zonedParts, type SourceBadge } from "@/lib/household";

export type HourBar = {
  label: string;
  key: string;
  solarUsed: number;
  exported: number;
  imported: number;
  pv: number | null;
  demand: number | null;
  missing: boolean;
  source: SourceBadge | null;
};

export type PlacedLoad = {
  load: Load;
  start: string;
  end: string;
  pvKwh: number;
  status: "recommended" | "partial" | "manual" | "unplaced";
};

export type PlanModel = {
  status: "empty" | "ready" | "low-solar" | "paused";
  placed: PlacedLoad[];
  flexibleKwh: number;
  pvKwh: number;
  windowLabel: string | null;
  /** Highest hour where planned load kW exceeds that hour's forecast PV. */
  overload: { hour: string; loadKw: number; pvKw: number } | null;
};

export type DerivedAlert = {
  id: string;
  level: "warning" | "info";
  title: string;
  detail: string;
  firstSeen: string;
  source: SourceBadge;
  kwhGap: number | null;
  day: string | null;
};

function rowsFor(rows: ForecastRow[], target: string) {
  return rows.filter((row) => row.target === target && Number.isFinite(Number(row.value_kw)));
}

function atKey(rows: ForecastRow[], key: string, timeZone: string) {
  return rows.find((row) => zonedParts(row.timestamp, timeZone).key === key) ?? null;
}

export function addDays(day: string, amount: number): string {
  const [year, month, date] = day.split("-").map(Number);
  const next = new Date(Date.UTC(year, month - 1, date + amount));
  return next.toISOString().slice(0, 10);
}

export function todayKey(timeZone: string, now = new Date()): string {
  return zonedParts(now.toISOString(), timeZone).day;
}

function hourKey(day: string, hour: number) {
  return `${day}-${String(hour).padStart(2, "0")}`;
}

function flows(pv: number | null, demand: number | null, net: number | null) {
  if (pv === null && demand === null && net === null) return null;
  const solar = pv ?? 0;
  const used = demand ?? 0;
  const netKw = net ?? used - solar;
  return {
    solarUsed: Math.max(0, Math.min(solar, used)),
    exported: Math.max(0, -netKw),
    imported: Math.max(0, netKw),
    pv,
    demand,
  };
}

export function hoursForDay(rows: ForecastRow[], timeZone: string, day: string): HourBar[] {
  const pv = rowsFor(rows, "pv");
  const demand = rowsFor(rows, "demand");
  const net = rowsFor(rows, "net");
  return Array.from({ length: 24 }, (_, hour) => {
    const key = hourKey(day, hour);
    const pvRow = atKey(pv, key, timeZone);
    const demandRow = atKey(demand, key, timeZone);
    const netRow = atKey(net, key, timeZone);
    const present = [pvRow, demandRow, netRow].filter((row): row is ForecastRow => row !== null);
    const flow = flows(
      pvRow ? Number(pvRow.value_kw) : null,
      demandRow ? Number(demandRow.value_kw) : null,
      netRow ? Number(netRow.value_kw) : null,
    );
    return {
      label: `${String(hour).padStart(2, "0")}:00`,
      key,
      solarUsed: flow?.solarUsed ?? 0,
      exported: flow?.exported ?? 0,
      imported: flow?.imported ?? 0,
      pv: flow?.pv ?? null,
      demand: flow?.demand ?? null,
      missing: present.length === 0,
      source: present[0] ? sourceBadge(present[0]) : null,
    };
  });
}

export function sumHours(hours: HourBar[]) {
  const known = hours.filter((hour) => !hour.missing);
  if (known.length === 0) return null;
  return known.reduce(
    (total, hour) => ({
      solarUsed: total.solarUsed + hour.solarUsed,
      exported: total.exported + hour.exported,
      imported: total.imported + hour.imported,
      pv: total.pv + (hour.pv ?? 0),
      demand: total.demand + (hour.demand ?? 0),
    }),
    { solarUsed: 0, exported: 0, imported: 0, pv: 0, demand: 0 },
  );
}

export function rangeDays(start: string, end: string): string[] {
  const days: string[] = [];
  let cursor = start;
  while (cursor <= end && days.length < 31) {
    days.push(cursor);
    cursor = addDays(cursor, 1);
  }
  return days;
}

export function dayLabel(day: string, timeZone: string): string {
  const [year, month, date] = day.split("-").map(Number);
  return new Intl.DateTimeFormat("en-GB", {
    timeZone,
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(Date.UTC(year, month - 1, date, 12)));
}

function parseClock(clock: string) {
  const [hour, minute] = clock.split(":").map(Number);
  return (hour || 0) * 60 + (minute || 0);
}

export function buildPlan(rows: ForecastRow[], timeZone: string, loads: Load[], paused: boolean): PlanModel {
  const pv = rowsFor(rows, "pv")
    .map((row) => ({ row, parts: zonedParts(row.timestamp, timeZone), ms: new Date(row.timestamp).getTime() }))
    .sort((a, b) => a.ms - b.ms);
  const pvKwh = pv.reduce((sum, item) => sum + Number(item.row.value_kw), 0);
  const flexible = loads.filter((load) => !load.manualOnly);
  const flexibleKwh = flexible.reduce((sum, load) => sum + loadEnergyKwh(load), 0);
  if (paused) {
    return { status: "paused", placed: [], flexibleKwh, pvKwh, windowLabel: null, overload: null };
  }
  if (loads.length === 0) {
    return { status: "empty", placed: [], flexibleKwh: 0, pvKwh, windowLabel: null, overload: null };
  }
  const usedKw = new Array(pv.length).fill(0);
  const ordered = [...loads].sort((a, b) => loadEnergyKwh(b) - loadEnergyKwh(a));
  const placed: PlacedLoad[] = ordered.map((load) => {
    if (load.manualOnly) {
      return { load, start: load.earliest, end: load.deadline, pvKwh: 0, status: "manual" };
    }
    const duration = Math.max(1, Math.round(load.minutes / 60));
    const loadKw = load.watts / 1000;
    const earliest = parseClock(load.earliest);
    const deadline = parseClock(load.deadline);
    let best: { index: number; pvKwh: number } | null = null;
    for (let index = 0; index <= pv.length - duration; index += 1) {
      const block = pv.slice(index, index + duration);
      const startParts = block[0].parts.clock.split(":").map(Number);
      const start = startParts[0] * 60 + startParts[1];
      const end = start + duration * 60;
      if (start < earliest || end > deadline + 60) continue;
      const fits = block.every((item, offset) => Number(item.row.value_kw) + 0.05 >= usedKw[index + offset] + loadKw);
      if (!fits) continue;
      const blockPv = block.reduce((sum, item) => sum + Number(item.row.value_kw), 0);
      if (!best || blockPv > best.pvKwh) best = { index, pvKwh: blockPv };
    }
    if (!best) return { load, start: load.earliest, end: load.deadline, pvKwh: 0, status: "unplaced" as const };
    for (let offset = 0; offset < duration; offset += 1) usedKw[best.index + offset] += loadKw;
    const block = pv.slice(best.index, best.index + duration);
    const energy = loadEnergyKwh(load);
    return {
      load,
      start: block[0].parts.clock,
      end: block[block.length - 1].parts.clock.replace(/^\d+/, (hour) => String(Number(hour) + 1).padStart(2, "0")),
      pvKwh: best.pvKwh,
      status: best.pvKwh >= energy ? "recommended" as const : "partial" as const,
    };
  });
  let overload: PlanModel["overload"] = null;
  pv.forEach((item, index) => {
    const pvKw = Number(item.row.value_kw);
    if (usedKw[index] > pvKw + 0.05 && !overload) {
      overload = { hour: item.parts.clock, loadKw: usedKw[index], pvKw };
    }
  });
  const usable = placed.filter((item) => item.status === "recommended" || item.status === "partial");
  const low = flexible.length > 0 && usable.length === 0;
  const window = usable[0] ? `${usable[0].start} – ${usable[0].end}` : null;
  return { status: low ? "low-solar" : "ready", placed, flexibleKwh, pvKwh, windowLabel: window, overload };
}

export function buildAlerts(rows: ForecastRow[], timeZone: string, now = new Date()): DerivedAlert[] {
  const alerts: DerivedAlert[] = [];
  const issued = rows[0]?.issued_at ?? null;
  const estimated: SourceBadge = { kind: "estimated", text: "Estimated" };
  if (!issued || isStale(issued, now.getTime())) {
    alerts.push({
      id: "stale-forecast",
      level: "warning",
      title: "Forecast is stale",
      detail: issued
        ? `The latest forecast was issued ${issued}. This is not a meter alarm.`
        : "This home has no forecast yet. This is not a meter alarm.",
      firstSeen: issued ?? now.toISOString(),
      source: estimated,
      kwhGap: null,
      day: null,
    });
  }
  const nowParts = zonedParts(now.toISOString(), timeZone);
  const hasNow = rows.some((row) => zonedParts(row.timestamp, timeZone).key === nowParts.key);
  if (rows.length > 0 && !hasNow) {
    alerts.push({
      id: "missing-hour",
      level: "info",
      title: "No forecast for this hour",
      detail: `The latest forecast has no row for ${nowParts.day} ${nowParts.clock}. History marks that same hour as "No forecast". Readings are not available with this key.`,
      firstSeen: issued ?? now.toISOString(),
      source: estimated,
      kwhGap: null,
      day: nowParts.day,
    });
  }
  const pv = rowsFor(rows, "pv");
  const today = zonedParts(now.toISOString(), timeZone).day;
  const todayPv = pv.filter((row) => zonedParts(row.timestamp, timeZone).day === today);
  const forecastSum = todayPv.reduce((sum, row) => sum + Number(row.value_kw), 0);
  const baselineSum = todayPv.reduce((sum, row) => sum + (row.baseline_kw ?? 0), 0);
  const hasBaseline = todayPv.some((row) => row.baseline_kw !== null);
  if (hasBaseline && baselineSum > 0 && forecastSum < baselineSum * 0.6) {
    alerts.push({
      id: "below-baseline",
      level: "warning",
      title: "Forecast PV is below the baseline",
      detail: `Today's PV forecast is ${forecastSum.toFixed(1)} kWh against a ${baselineSum.toFixed(1)} kWh baseline. This compares two forecasts. It is not a measured fault.`,
      firstSeen: issued ?? now.toISOString(),
      source: estimated,
      kwhGap: Math.round((baselineSum - forecastSum) * 10) / 10,
      day: today,
    });
  }
  return alerts;
}
