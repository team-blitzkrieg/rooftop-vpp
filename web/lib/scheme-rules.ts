export type Scheme = "net-metering" | "net-accounting" | "net-plus";
export type ConnectionKind = "new" | "existing";

export const SCHEME_RULE_DATE = "2026-09-11";
export const RATES_EFFECTIVE = "2026-08-25";
/** Reported by a secondary source. The PUCSL decision says "until the next tariff revision". */
export const RATES_REPORTED_VALID_TO = "2027-02-24";

export const FEED_IN_LKR = [
  { upToKw: 10, lkrPerKwh: 23.11 },
  { upToKw: 40, lkrPerKwh: 19.15 },
  { upToKw: 250, lkrPerKwh: 17.11 },
  { upToKw: Number.POSITIVE_INFINITY, lkrPerKwh: 15.81 },
] as const;

export function feedInLkr(systemKw: number): number {
  const band = FEED_IN_LKR.find((row) => systemKw <= row.upToKw);
  return band?.lkrPerKwh ?? 15.81;
}

export function ratesWithin30Days(now = new Date()): boolean {
  const end = Date.parse(`${RATES_REPORTED_VALID_TO}T00:00:00+05:30`);
  return (end - now.getTime()) / 86_400_000 <= 30;
}

/** Moving use into sunny hours changes the bill only for existing Net Accounting. */
export function timingChangesBill(scheme: Scheme | null | undefined): boolean {
  return scheme === "net-accounting";
}

export function schemeLabel(scheme: Scheme): string {
  if (scheme === "net-plus") return "Net Plus";
  if (scheme === "net-accounting") return "Net Accounting";
  return "Net Metering";
}

export function schemeWhy(scheme: Scheme): string {
  if (scheme === "net-plus") {
    return "Under Net Plus the forecast export is paid at the feed-in rate, and the home pays for what it uses. Shifting appliances does not change that bill.";
  }
  if (scheme === "net-metering") {
    return "Under Net Metering, exported units bank one for one. Moving use in time changes the bill by about zero. This screen stays in kWh.";
  }
  return "Under Net Accounting, using solar at home can avoid a higher buy rate. Any rupee figure below subtracts lost export income and is labelled as an assumption.";
}
