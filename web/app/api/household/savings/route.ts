import { feedInLkr, schemeWhy, type Scheme } from "@/lib/scheme-rules";
import { publicServerClient } from "@/lib/server-supabase";

export const dynamic = "force-dynamic";

const SCHEMES = new Set<Scheme>(["net-metering", "net-accounting", "net-plus"]);

/** Forecast arithmetic. Not a bill. */
export async function GET(request: Request) {
  const url = new URL(request.url);
  const site = url.searchParams.get("site")?.trim();
  const schemeRaw = url.searchParams.get("scheme") ?? "net-plus";
  if (!site) return Response.json({ error: "site is required" }, { status: 422 });
  if (!SCHEMES.has(schemeRaw as Scheme)) return Response.json({ error: "Unknown scheme" }, { status: 422 });
  const scheme = schemeRaw as Scheme;
  const systemKw = Number(url.searchParams.get("system_kw") || "3");
  const supabase = publicServerClient();
  if (!supabase) return Response.json({ error: "Forecast read is not configured" }, { status: 503 });
  const latest = await supabase.from("forecasts").select("issued_at").eq("site_id", site).order("issued_at", { ascending: false }).limit(1);
  const issued = latest.data?.[0]?.issued_at as string | undefined;
  if (!issued) {
    return Response.json({ site_id: site, scheme, kwh: null, lkr: null, controls_equipment: false });
  }
  const rows = await supabase
    .from("forecasts")
    .select("target,value_kw,data_label,is_simulated")
    .eq("site_id", site)
    .eq("issued_at", issued)
    .eq("target", "pv");
  const kwh = Math.round((rows.data ?? []).reduce((sum, row) => sum + Number(row.value_kw), 0) * 10) / 10;
  const fit = feedInLkr(systemKw > 0 ? systemKw : 5);
  const simulated = (rows.data ?? []).some((row) => row.is_simulated || row.data_label === "SIMULATED");
  const lkr = scheme === "net-plus" ? Math.round(kwh * fit) : null;
  return Response.json({
    site_id: site,
    scheme,
    kwh,
    lkr,
    feed_in_lkr: fit,
    note: scheme === "net-metering" ? "kWh only. No rupee saving." : schemeWhy(scheme),
    data_label: simulated ? "SIMULATED" : "ESTIMATED",
    controls_equipment: false,
  });
}
