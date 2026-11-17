import { createClient, type SupabaseClient } from "@supabase/supabase-js";

/** Browser client. Uses the public publishable key only. */
export function browserSupabase(): SupabaseClient | null {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
  if (!url || !key) return null;
  return createClient(url, key);
}
