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
