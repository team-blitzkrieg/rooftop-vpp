import type { User } from "@supabase/supabase-js";
import { EMPTY, type DemoState, type Load } from "@/lib/demo-store";
import { browserSupabase } from "@/lib/supabase";

/** Load the signed-in Supabase user into the same shape the screens already use. */
export async function hydrateFromAuth(): Promise<DemoState | null> {
  const supabase = browserSupabase();
  if (!supabase) return null;
  const { data } = await supabase.auth.getSession();
  const user = data.session?.user;
  if (!user) return null;
  return pullAccount(user);
}

export async function pullAccount(user: User): Promise<DemoState> {
  const supabase = browserSupabase();
  const session = {
    email: user.email ?? "",
    signedInAt: new Date().toISOString(),
    mode: "auth" as const,
    userId: user.id,
  };
  const base: DemoState = { ...EMPTY, session, loads: [], seenAlerts: [] };
  if (!supabase) return base;
  const [profile, consent, loads, participation, seen] = await Promise.all([
    supabase.from("profiles").select("*").eq("user_id", user.id).maybeSingle(),
    supabase.from("consents").select("*").eq("user_id", user.id).order("agreed_at", { ascending: false }).limit(1),
    supabase.from("loads").select("*").eq("user_id", user.id),
    supabase.from("participation").select("*").eq("user_id", user.id).maybeSingle(),
    supabase.from("seen_alerts").select("alert_id").eq("user_id", user.id),
  ]);
  if (profile.error || consent.error || loads.error || participation.error || seen.error) return base;
  const row = profile.data;
  if (row) {
    base.profile = {
      connection: row.connection === "existing" ? "existing" : "new",
      scheme: row.scheme === "net-metering" || row.scheme === "net-accounting" ? row.scheme : "net-plus",
      tariffLabel: row.tariff_label ?? "",
      systemKw: row.system_kw == null ? "" : String(row.system_kw),
      effective: row.effective ?? "",
      agreementEnds: row.agreement_ends ?? "",
      touMeter: Boolean(row.tou_meter),
    };
    base.notifyAlerts = row.notify_alerts !== false;
  }
  const agreed = consent.data?.[0];
  if (agreed && !agreed.withdrawn_at) {
    base.consent = {
      version: agreed.version,
      agreedAt: agreed.agreed_at,
      scopes: { solar: false, grid: false, home: false, appliance: false, totals: false, ...(agreed.scopes ?? {}) },
    };
  }
  if (agreed?.withdrawn_at && agreed.receipt_id) {
    base.withdrawReceipt = {
      id: agreed.receipt_id,
      email: session.email,
      at: agreed.withdrawn_at,
      deleteBy: agreed.withdrawn_at,
    };
  }
  base.loads = (loads.data ?? []).map(toLoad);
  if (participation.data) {
    base.paused = Boolean(participation.data.paused);
    base.pausedAt = participation.data.paused_at;
    base.skipDay = participation.data.skip_day;
  }
  base.seenAlerts = (seen.data ?? []).map((item) => item.alert_id as string);
  return base;
}

export async function rememberSite(userId: string, siteId: string): Promise<void> {
  const supabase = browserSupabase();
  if (!supabase || !siteId) return;
  await supabase.from("profiles").upsert(
    { user_id: userId, site_id: siteId, updated_at: new Date().toISOString() },
    { onConflict: "user_id" },
  );
}

export async function pushAccount(state: DemoState): Promise<void> {
  const userId = state.session?.mode === "auth" ? state.session.userId : null;
  const supabase = browserSupabase();
  if (!userId || !supabase) return;
  const profile = state.profile;
  await supabase.from("profiles").upsert({
    user_id: userId,
    email: state.session?.email ?? null,
    connection: profile?.connection ?? "new",
    scheme: profile?.scheme ?? "net-plus",
    tariff_label: profile?.tariffLabel ?? null,
    system_kw: profile?.systemKw ? Number(profile.systemKw) : null,
    effective: profile?.effective || null,
    agreement_ends: profile?.agreementEnds || null,
    tou_meter: Boolean(profile?.touMeter),
    notify_alerts: state.notifyAlerts,
    updated_at: new Date().toISOString(),
  });
  if (state.consent) {
    const existing = await supabase
      .from("consents")
      .select("consent_id,withdrawn_at")
      .eq("user_id", userId)
      .order("agreed_at", { ascending: false })
      .limit(1);
    const current = existing.data?.[0];
    if (!current) {
      await supabase.from("consents").insert({
        user_id: userId,
        version: state.consent.version,
        agreed_at: state.consent.agreedAt,
        scopes: state.consent.scopes,
      });
    } else if (state.withdrawReceipt && !current.withdrawn_at) {
      await supabase
        .from("consents")
        .update({ withdrawn_at: state.withdrawReceipt.at, receipt_id: state.withdrawReceipt.id })
        .eq("consent_id", current.consent_id);
    }
  }
  await supabase.from("loads").delete().eq("user_id", userId);
  if (state.loads.length) {
    await supabase.from("loads").insert(
      state.loads.map((load) => ({
        load_id: load.id,
        user_id: userId,
        name: load.name,
        watts: load.watts,
        minutes: load.minutes,
        earliest: load.earliest,
        deadline: load.deadline,
        interruptible: load.interruptible,
        manual_only: load.manualOnly,
      })),
    );
  }
  await supabase.from("participation").upsert({
    user_id: userId,
    paused: state.paused,
    paused_at: state.pausedAt,
    skip_day: state.skipDay,
    updated_at: new Date().toISOString(),
  });
  if (state.seenAlerts.length) {
    await supabase.from("seen_alerts").upsert(
      state.seenAlerts.map((alertId) => ({ user_id: userId, alert_id: alertId })),
      { onConflict: "user_id,alert_id" },
    );
  }
}

function toLoad(row: Record<string, unknown>): Load {
  return {
    id: String(row.load_id),
    name: String(row.name ?? ""),
    watts: Number(row.watts ?? 0),
    minutes: Number(row.minutes ?? 0),
    earliest: String(row.earliest ?? "08:00"),
    deadline: String(row.deadline ?? "18:00"),
    interruptible: Boolean(row.interruptible),
    manualOnly: Boolean(row.manual_only),
  };
}
