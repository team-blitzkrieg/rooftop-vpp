-- Apply in the Supabase SQL editor if the project already has api/schema.sql
-- from before 17 Nov 2026. Safe to run more than once.
-- A brand-new project can paste api/schema.sql instead; it includes this section.

-- Household account, consent, advice state, coordinator cases, fault checks.
-- user_id is a Supabase Auth user. There is no foreign key to auth.users,
-- so this file still applies on plain Postgres. Advice rows never store a setpoint.

create table if not exists profiles (
    user_id uuid primary key,
    email text,
    site_id text references sites (site_id),
    connection text not null default 'new' check (connection in ('new', 'existing')),
    scheme text not null default 'net-plus' check (scheme in ('net-metering', 'net-accounting', 'net-plus')),
    tariff_label text,
    system_kw double precision,
    effective date,
    agreement_ends date,
    tou_meter boolean not null default false,
    notify_alerts boolean not null default true,
    updated_at timestamptz not null default now()
);

create table if not exists consents (
    consent_id bigserial primary key,
    user_id uuid not null,
    version text not null,
    agreed_at timestamptz not null default now(),
    scopes jsonb not null,
    withdrawn_at timestamptz,
    receipt_id text
);

create index if not exists consents_user_idx on consents (user_id, agreed_at desc);

create table if not exists loads (
    load_id text primary key,
    user_id uuid not null,
    name text not null,
    watts integer not null check (watts >= 0),
    minutes integer not null check (minutes >= 0),
    earliest text not null,
    deadline text not null,
    interruptible boolean not null default true,
    manual_only boolean not null default false
);

create index if not exists loads_user_idx on loads (user_id);

create table if not exists participation (
    user_id uuid primary key,
    paused boolean not null default false,
    paused_at timestamptz,
    skip_day date,
    updated_at timestamptz not null default now()
);

create table if not exists seen_alerts (
    user_id uuid not null,
    alert_id text not null,
    seen_at timestamptz not null default now(),
    primary key (user_id, alert_id)
);

create table if not exists site_assignments (
    site_id text primary key references sites (site_id),
    coordinator_id uuid,
    note text,
    assigned_at timestamptz not null default now()
);

create table if not exists cases (
    case_id bigserial primary key,
    site_id text not null references sites (site_id),
    opened_by uuid,
    title text not null,
    status text not null default 'open' check (status in ('open', 'closed')),
    detail text,
    opened_at timestamptz not null default now(),
    closed_at timestamptz
);

create index if not exists cases_site_idx on cases (site_id, status);

create table if not exists fault_results (
    site_id text not null references sites (site_id),
    rule text not null,
    status text not null,
    detail text,
    checked_at timestamptz not null default now(),
    data_label text not null default 'NOT_AVAILABLE',
    is_simulated boolean not null default false,
    primary key (site_id, rule)
);

create table if not exists ingest_hits (
    hit_id bigserial primary key,
    site_id text not null,
    hit_at timestamptz not null default now()
);

create index if not exists ingest_hits_site_idx on ingest_hits (site_id, hit_at desc);

alter table profiles enable row level security;
alter table consents enable row level security;
alter table loads enable row level security;
alter table participation enable row level security;
alter table seen_alerts enable row level security;
alter table site_assignments enable row level security;
alter table cases enable row level security;
alter table fault_results enable row level security;
alter table ingest_hits enable row level security;

do $$
begin
    if exists (select 1 from pg_roles where rolname = 'anon') then
        execute 'drop policy if exists fault_results_anon_select on fault_results';
        execute 'create policy fault_results_anon_select on fault_results for select to anon using (true)';
    end if;
    if exists (select 1 from pg_namespace where nspname = 'auth')
       and exists (select 1 from pg_roles where rolname = 'authenticated') then
        execute 'drop policy if exists profiles_own on profiles';
        execute 'create policy profiles_own on profiles for all to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid())';
        execute 'drop policy if exists consents_own on consents';
        execute 'create policy consents_own on consents for all to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid())';
        execute 'drop policy if exists loads_own on loads';
        execute 'create policy loads_own on loads for all to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid())';
        execute 'drop policy if exists participation_own on participation';
        execute 'create policy participation_own on participation for all to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid())';
        execute 'drop policy if exists seen_alerts_own on seen_alerts';
        execute 'create policy seen_alerts_own on seen_alerts for all to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid())';
        execute 'drop policy if exists assignments_read on site_assignments';
        execute 'create policy assignments_read on site_assignments for select to authenticated using (true)';
        execute 'drop policy if exists cases_read on cases';
        execute 'create policy cases_read on cases for select to authenticated using (true)';
        execute 'drop policy if exists cases_insert on cases';
        execute 'create policy cases_insert on cases for insert to authenticated with check (opened_by = auth.uid())';
        execute 'drop policy if exists cases_update on cases';
        execute 'create policy cases_update on cases for update to authenticated using (opened_by = auth.uid()) with check (opened_by = auth.uid())';
        execute 'drop policy if exists readings_owner_select on readings';
        execute 'create policy readings_owner_select on readings for select to authenticated using (site_id = (select site_id from profiles where user_id = auth.uid()))';
    end if;
end $$;

