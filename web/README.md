# Household forecast page

One page. It reads `sites` and `forecasts` from Supabase in the browser and draws the next 48 hours. It polls once an hour. It does not sign anyone in, and it does not control equipment.

## Vercel

Create a **new** Vercel project for this directory. Do not point it at the repository root.

The repository root `vercel.json` sets `ignoreCommand` to `exit 0`. That project skips every build so Vercel does not bundle the Python tree into a serverless function. A project whose Root Directory is `web` uses `web/vercel.json` instead. That file has no `ignoreCommand`, so this Next.js app builds.

Settings:

- Root Directory: `web`
- Framework: Next.js
- Environment variables (Production and Preview):
  - `NEXT_PUBLIC_SUPABASE_URL` = `https://nwmacpgyhebjcvebmrxt.supabase.co`
  - `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` = the publishable key from Supabase (Project Settings → API). This is the anon key. Do not use the service role key.

Copy `web/.env.example` to `web/.env.local` for a laptop. The same two names.

The page stays empty until someone runs the **Seed demo** workflow. See `DEPLOY.md`.
