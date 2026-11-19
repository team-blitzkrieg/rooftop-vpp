import { createClient } from "@supabase/supabase-js";

export const dynamic = "force-dynamic";

/** Assignments and open cases. The caller's Supabase access token is required. */
export async function GET(request: Request) {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL || process.env.SUPABASE_URL || "";
  const key = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY || "";
  const token = (request.headers.get("authorization") ?? "").replace(/^Bearer\s+/i, "").trim();
  if (!url || !key || key === "public-build-placeholder") {
    return Response.json({ assignments: [], cases: [], source: "unconfigured", controls_equipment: false });
  }
  if (!token) {
    return Response.json({ assignments: [], cases: [], source: "signed-out", controls_equipment: false });
  }
  const supabase = createClient(url, key, {
    auth: { persistSession: false, autoRefreshToken: false },
    global: { headers: { Authorization: `Bearer ${token}` } },
  });
  const [assignments, cases] = await Promise.all([
    supabase.from("site_assignments").select("site_id,coordinator_id,note,assigned_at"),
    supabase.from("cases").select("case_id,site_id,title,status,detail,opened_at").eq("status", "open"),
  ]);
  if (assignments.error || cases.error) {
    return Response.json({
      assignments: [],
      cases: [],
      source: "missing-table",
      controls_equipment: false,
    });
  }
  return Response.json({
    assignments: assignments.data ?? [],
    cases: cases.data ?? [],
    source: "database",
    controls_equipment: false,
  });
}
