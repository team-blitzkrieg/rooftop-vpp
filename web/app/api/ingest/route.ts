import { createHash } from "node:crypto";
import { INGEST_LIMIT_PER_MINUTE, parseIngestBody, rateDecision } from "@/lib/ingest-contract";
import { serviceServerClient } from "@/lib/server-supabase";

export const dynamic = "force-dynamic";

/** Pi edge unit. Header X-Device-Key or Authorization: Bearer. Does not command the inverter. */
export async function POST(request: Request) {
  const token = deviceToken(request);
  if (!token) {
    return Response.json({ error: "X-Device-Key is required", controls_equipment: false }, { status: 401 });
  }
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return Response.json({ error: "Body must be JSON", controls_equipment: false }, { status: 422 });
  }
  const parsed = parseIngestBody(body);
  if (!parsed.ok) {
    return Response.json({ error: parsed.error, controls_equipment: false }, { status: parsed.status });
  }
  const admin = serviceServerClient();
  if (!admin) {
    return Response.json(
      { error: "SUPABASE_SERVICE_ROLE_KEY is not set on the server", controls_equipment: false },
      { status: 503 },
    );
  }
  const hash = createHash("sha256").update(token).digest("hex");
  const device = await admin.from("devices").select("site_id").eq("key_sha256", hash).maybeSingle();
  if (device.error) {
    return Response.json({ error: "Device lookup failed", controls_equipment: false }, { status: 503 });
  }
  if (!device.data?.site_id) {
    return Response.json({ error: "Unknown device key", controls_equipment: false }, { status: 401 });
  }
  const siteId = device.data.site_id as string;
  const since = new Date(Date.now() - 60_000).toISOString();
  const recent = await admin
    .from("ingest_hits")
    .select("hit_id", { count: "exact", head: true })
    .eq("site_id", siteId)
    .gte("hit_at", since);
  if (recent.error) {
    return Response.json(
      { error: "Rate-limit table is missing. Apply api/migrations/2026-11-17-household.sql", controls_equipment: false },
      { status: 503 },
    );
  }
  if (rateDecision(recent.count ?? 0, INGEST_LIMIT_PER_MINUTE) === "limited") {
    return Response.json({ error: "Too many requests for this site", controls_equipment: false }, { status: 429 });
  }
  await admin.from("ingest_hits").insert({ site_id: siteId });
  await admin.from("ingest_hits").delete().eq("site_id", siteId).lt("hit_at", new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString());
  const rows = parsed.readings.map((reading) => ({ site_id: siteId, ...reading }));
  const saved = await admin.from("readings").upsert(rows, { onConflict: "site_id,timestamp" });
  if (saved.error) {
    return Response.json({ error: "Could not store readings", controls_equipment: false }, { status: 503 });
  }
  return Response.json({
    site_id: siteId,
    upserted: rows.length,
    data_label: rows.every((row) => row.data_label === "SIMULATED") ? "SIMULATED" : rows[0].data_label,
    controls_equipment: false,
  });
}

function deviceToken(request: Request): string {
  const header = request.headers.get("x-device-key")?.trim();
  if (header) return header;
  const auth = request.headers.get("authorization") ?? "";
  const match = auth.match(/^Bearer\s+(.+)$/i);
  return match?.[1]?.trim() ?? "";
}
