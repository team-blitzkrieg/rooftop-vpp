export type SiteRow = {
  site_id: string;
  name: string | null;
  timezone: string;
};

export type ForecastRow = {
  target: string;
  timestamp: string;
  issued_at: string;
  value_kw: number;
  baseline_kw: number | null;
  model_version: string;
  data_label: string;
  is_simulated: boolean;
};

export type ChartPoint = {
  timestamp: string;
  label: string;
  pv: number | null;
  pvBase: number | null;
  demand: number | null;
  demandBase: number | null;
  net: number | null;
  netBase: number | null;
};

const STALE_MS = 26 * 60 * 60 * 1000;
const EVENING_START = 18 * 60 + 30;
const EVENING_END = 22 * 60;

export function isStale(issuedAt: string, now = Date.now()): boolean {
  const issued = new Date(issuedAt).getTime();
  return Number.isFinite(issued) && now - issued > STALE_MS;
}

export function isSimulated(rows: ForecastRow[]): boolean {
  return rows.some((row) => row.data_label === "SIMULATED" || row.is_simulated);
}

type Zoned = {
  date: string;
  minutes: number;
  axis: string;
  clock: string;
};

function zoned(iso: string, timeZone: string): Zoned {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone,
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(new Date(iso));
  const get = (type: string) => parts.find((part) => part.type === type)?.value ?? "";
  const hour = Number(get("hour"));
  const minute = Number(get("minute"));
  return {
    date: `${get("year")}-${get("month")}-${get("day")}`,
    minutes: hour * 60 + minute,
    axis: `${get("day")} ${get("month")} ${get("hour")}:${get("minute")}`,
    clock: `${get("hour")}:${get("minute")}`,
  };
}

export function todayKey(timeZone: string, now = new Date()): string {
  return zoned(now.toISOString(), timeZone).date;
}

export function sumKwh(rows: ForecastRow[], timeZone: string, day: string): number | null {
  const hours = rows.filter((row) => zoned(row.timestamp, timeZone).date === day);
  if (hours.length === 0) return null;
  return hours.reduce((total, row) => total + Number(row.value_kw), 0);
}

export function eveningPeak(rows: ForecastRow[], timeZone: string): string | null {
  let best: { value: number; label: string } | null = null;
  for (const row of rows) {
    const when = zoned(row.timestamp, timeZone);
    if (when.minutes < EVENING_START || when.minutes >= EVENING_END) continue;
    const value = Number(row.value_kw);
    if (best === null || value > best.value) {
      best = { value, label: `${when.axis.split(" ").slice(0, 2).join(" ")} ${when.clock}` };
    }
  }
  return best?.label ?? null;
}

export function chartPoints(rows: ForecastRow[], timeZone: string): ChartPoint[] {
  const byTime = new Map<string, ChartPoint>();
  for (const row of rows) {
    const when = zoned(row.timestamp, timeZone);
    const point = byTime.get(row.timestamp) ?? {
      timestamp: row.timestamp,
      label: when.axis,
      pv: null,
      pvBase: null,
      demand: null,
      demandBase: null,
      net: null,
      netBase: null,
    };
    const value = Number(row.value_kw);
    const baseline = row.baseline_kw === null ? null : Number(row.baseline_kw);
    if (row.target === "pv") {
      point.pv = value;
      point.pvBase = baseline;
    } else if (row.target === "demand") {
      point.demand = value;
      point.demandBase = baseline;
    } else if (row.target === "net") {
      point.net = value;
      point.netBase = baseline;
    }
    byTime.set(row.timestamp, point);
  }
  return [...byTime.values()].sort((a, b) => a.timestamp.localeCompare(b.timestamp));
}

export function formatKwh(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "—";
  return `${value.toFixed(1)} kWh`;
}

export function formatIssued(iso: string, timeZone: string): string {
  return new Intl.DateTimeFormat("en-GB", {
    timeZone,
    dateStyle: "medium",
    timeStyle: "short",
    hourCycle: "h23",
  }).format(new Date(iso));
}
