import { createClient, type SupabaseClient } from "@supabase/supabase-js";

function url(): string {
  return process.env.NEXT_PUBLIC_SUPABASE_URL || process.env.SUPABASE_URL || "";
}

/** Anon key. Safe for forecast reads. Never the service role. */
export function publicServerClient(): SupabaseClient | null {
  const key = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY || "";
  if (!url() || !key || key === "public-build-placeholder") return null;
  return createClient(url(), key, { auth: { persistSession: false, autoRefreshToken: false } });
}

/** Server only. Set SUPABASE_SERVICE_ROLE_KEY on Vercel. Do not prefix it with NEXT_PUBLIC_. */
export function serviceServerClient(): SupabaseClient | null {
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY || "";
  if (!url() || !key) return null;
  return createClient(url(), key, { auth: { persistSession: false, autoRefreshToken: false } });
}
