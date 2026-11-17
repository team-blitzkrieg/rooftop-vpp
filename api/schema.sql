-- Plain Postgres for the Supabase free project.
-- Timescale is used only when the extension is already installed.
-- The API does not command inverters. Forecasts are for the scheduler to read.

create extension if not exists pgcrypto;

create table if not exists sites (
    site_id text primary key,
    name text,
    timezone text not null default 'Asia/Colombo',
    system_kw double precision,
    tilt_deg double precision,
    azimuth_deg double precision,
    latitude double precision,
    longitude double precision,
    has_meter boolean not null default true,
    demand_scale_kw double precision
);

create table if not exists devices (
    device_id text primary key,
    site_id text not null references sites (site_id),
    key_sha256 text not null unique,
    created_at timestamptz not null default now()
);

create table if not exists readings (
    site_id text not null references sites (site_id),
    timestamp timestamptz not null,
    pv_kw double precision,
    consumption_kw double precision,
    import_kw double precision,
    export_kw double precision,
    data_label text not null default 'MEASURED',
    is_simulated boolean not null default false,
    primary key (site_id, timestamp)
);

create index if not exists readings_site_time_idx
    on readings (site_id, timestamp desc);

create table if not exists forecast_runs (
    run_id bigserial primary key,
    site_id text not null,
    target text not null,
    issued_at timestamptz,
    status text not null check (status in ('success', 'failed')),
    model_version text,
    message text,
    created_at timestamptz not null default now()
);

create index if not exists forecast_runs_site_idx
    on forecast_runs (site_id, target, created_at desc);

create table if not exists forecasts (
    site_id text not null,
    target text not null,
    timestamp timestamptz not null,
    issued_at timestamptz not null,
    lead_hours double precision,
    value_kw double precision not null,
    baseline_kw double precision,
    net_kw double precision,
    model_version text not null,
    run_id bigint references forecast_runs (run_id),
    resolution text,
    data_label text not null default 'SIMULATED',
    is_simulated boolean not null default true,
    primary key (site_id, target, timestamp, issued_at)
);

create index if not exists forecasts_site_time_idx
    on forecasts (site_id, target, timestamp desc);

create table if not exists model_versions (
    version text primary key,
    target text not null,
    metrics jsonb,
    promoted boolean not null default false,
    artefact_url text,
    git_sha text,
    created_at timestamptz not null default now()
);

create unique index if not exists one_promoted_model_per_target
    on model_versions (target)
    where promoted;

alter table sites enable row level security;
alter table devices enable row level security;
alter table readings enable row level security;
alter table forecast_runs enable row level security;
alter table forecasts enable row level security;
alter table model_versions enable row level security;

-- anon can read forecasts and model metadata. It cannot read meters or device keys.
do $$
begin
    if exists (select 1 from pg_roles where rolname = 'anon') then
        execute 'drop policy if exists forecasts_anon_select on forecasts';
        execute 'create policy forecasts_anon_select on forecasts for select to anon using (true)';
        execute 'drop policy if exists model_versions_anon_select on model_versions';
        execute 'create policy model_versions_anon_select on model_versions for select to anon using (true)';
        execute 'drop policy if exists sites_anon_select on sites';
        execute 'create policy sites_anon_select on sites for select to anon using (true)';
    end if;
end $$;

-- Direct insert from a meter: the key is checked inside the function.
-- The readings table has no insert policy for anon.
create or replace function ingest_reading(
    device_key text,
    reading_time timestamptz,
    pv double precision,
    consumption double precision,
    import_kw double precision,
    export_kw double precision
) returns void
language plpgsql
security definer
set search_path = public
as $$
declare
    found_site text;
begin
    select site_id into found_site
    from devices
    where key_sha256 = encode(digest(device_key, 'sha256'), 'hex');
    if found_site is null then
        raise exception 'unknown device key';
    end if;
    insert into readings (
        site_id, timestamp, pv_kw, consumption_kw, import_kw, export_kw, data_label, is_simulated
    )
    values (found_site, reading_time, pv, consumption, import_kw, export_kw, 'MEASURED', false)
    on conflict (site_id, timestamp) do update set
        pv_kw = excluded.pv_kw,
        consumption_kw = excluded.consumption_kw,
        import_kw = excluded.import_kw,
        export_kw = excluded.export_kw;
end $$;

do $$
begin
    if exists (select 1 from pg_roles where rolname = 'anon') then
        execute 'grant execute on function ingest_reading(text, timestamptz, double precision, double precision, double precision, double precision) to anon';
    end if;
end $$;

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

-- Optional. A free Supabase project usually does not have Timescale.
-- A failure here is ignored so the plain tables still work.
do $$
begin
    if exists (select 1 from pg_extension where extname = 'timescaledb') then
        begin
            perform create_hypertable('readings', 'timestamp', if_not_exists => true);
        exception when others then
            raise notice 'readings hypertable skipped: %', sqlerrm;
        end;
        begin
            perform create_hypertable('forecasts', 'timestamp', if_not_exists => true);
        exception when others then
            raise notice 'forecasts hypertable skipped: %', sqlerrm;
        end;
    end if;
end $$;
