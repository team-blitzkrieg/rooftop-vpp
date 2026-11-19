import { buildAlerts } from "@/lib/household-derive";
import { publicServerClient } from "@/lib/server-supabase";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const site = new URL(request.url).searchParams.get("site")?.trim();
  if (!site) return Response.json({ error: "site is required" }, { status: 422 });
  const supabase = publicServerClient();
  if (!supabase) return Response.json({ error: "Forecast read is not configured" }, { status: 503 });
  const latest = await supabase.from("forecasts").select("issued_at").eq("site_id", site).order("issued_at", { ascending: false }).limit(1);
  if (latest.error || !latest.data?.[0]?.issued_at) {
    return Response.json({ site_id: site, alerts: [], source: "server", controls_equipment: false });
  }
  const issued = latest.data[0].issued_at as string;
  const siteRow = await supabase.from("sites").select("timezone").eq("site_id", site).maybeSingle();
  const rows = await supabase
    .from("forecasts")
    .select("target,timestamp,issued_at,value_kw,baseline_kw,model_version,data_label,is_simulated")
    .eq("site_id", site)
    .eq("issued_at", issued);
  const zone = (siteRow.data?.timezone as string | undefined) || "Asia/Colombo";
  const alerts = buildAlerts(rows.data ?? [], zone);
  return Response.json({ site_id: site, source: "server", controls_equipment: false, alerts });
}
