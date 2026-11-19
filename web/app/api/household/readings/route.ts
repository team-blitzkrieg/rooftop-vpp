import { DEMO_SIM_SITE } from "@/lib/household";
import { serviceServerClient } from "@/lib/server-supabase";

export const dynamic = "force-dynamic";

const WEEK_MS = 7 * 24 * 60 * 60 * 1000;

/** Latest demo-sim readings. Other sites stay private. Does not command a device. */
export async function GET(request: Request) {
  const site = new URL(request.url).searchParams.get("site")?.trim();
  if (!site) return Response.json({ error: "site is required", controls_equipment: false }, { status: 422 });
  if (site !== DEMO_SIM_SITE) {
    return Response.json({
      site_id: site,
      rows: [],
      data_label: null,
      is_simulated: false,
      note: "Only the demo-sim home is shown here. Other meters stay private.",
      controls_equipment: false,
    });
  }
  const admin = serviceServerClient();
  if (!admin) {
    return Response.json(
      {
        error: "SUPABASE_SERVICE_ROLE_KEY is not set on the server",
        site_id: site,
        rows: [],
        controls_equipment: false,
      },
      { status: 503 },
    );
  }
  const since = new Date(Date.now() - WEEK_MS).toISOString();
  const rows = await admin
    .from("readings")
    .select("timestamp,pv_kw,consumption_kw,import_kw,export_kw,data_label,is_simulated")
    .eq("site_id", DEMO_SIM_SITE)
    .gte("timestamp", since)
    .order("timestamp", { ascending: false })
    .limit(48);
  if (rows.error) {
    return Response.json({ error: "Could not read demo readings", controls_equipment: false }, { status: 503 });
  }
  const list = rows.data ?? [];
  const simulated = list.every((row) => row.is_simulated || row.data_label === "SIMULATED");
  return Response.json({
    site_id: DEMO_SIM_SITE,
    data_label: simulated ? "SIMULATED" : "MIXED",
    is_simulated: simulated,
    controls_equipment: false,
    rows: list,
  });
}
