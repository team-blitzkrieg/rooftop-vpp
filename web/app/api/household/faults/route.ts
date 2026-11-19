import { publicServerClient } from "@/lib/server-supabase";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const site = new URL(request.url).searchParams.get("site")?.trim();
  const supabase = publicServerClient();
  if (!supabase) return Response.json({ error: "Forecast read is not configured" }, { status: 503 });
  let query = supabase.from("fault_results").select("site_id,rule,status,detail,checked_at,data_label,is_simulated");
  if (site) query = query.eq("site_id", site);
  const result = await query;
  if (result.error) {
    return Response.json({
      results: [],
      pending_migration: true,
      note: "Fault results are not in the database yet.",
      controls_equipment: false,
    });
  }
  return Response.json({ results: result.data ?? [], pending_migration: false, controls_equipment: false });
}
