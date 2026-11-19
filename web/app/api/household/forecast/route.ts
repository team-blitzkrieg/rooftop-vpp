import { isStale } from "@/lib/forecast";
import { publicServerClient } from "@/lib/server-supabase";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const site = new URL(request.url).searchParams.get("site")?.trim();
  if (!site) return Response.json({ error: "site is required" }, { status: 422 });
  const supabase = publicServerClient();
  if (!supabase) return Response.json({ error: "Forecast read is not configured" }, { status: 503 });
  const latest = await supabase
    .from("forecasts")
    .select("issued_at")
    .eq("site_id", site)
    .order("issued_at", { ascending: false })
    .limit(1);
  if (latest.error) return Response.json({ error: latest.error.message }, { status: 503 });
  const issued = latest.data?.[0]?.issued_at as string | undefined;
  if (!issued) {
    return Response.json({ site_id: site, issued_at: null, stale: true, rows: [], controls_equipment: false });
  }
  const rows = await supabase
    .from("forecasts")
    .select("target,timestamp,issued_at,value_kw,baseline_kw,model_version,data_label,is_simulated")
    .eq("site_id", site)
    .eq("issued_at", issued)
    .order("timestamp");
  if (rows.error) return Response.json({ error: rows.error.message }, { status: 503 });
  const list = rows.data ?? [];
  const label = (list[0]?.data_label as string | undefined) ?? "SIMULATED";
  return Response.json({
    site_id: site,
    issued_at: issued,
    stale: isStale(issued),
    data_label: label,
    is_simulated: label === "SIMULATED" || Boolean(list[0]?.is_simulated),
    controls_equipment: false,
    rows: list,
  });
}
