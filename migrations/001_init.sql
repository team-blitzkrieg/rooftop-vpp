-- Timescale on Postgres. The pilot stores readings and forecasts.
-- Nothing in this schema is a command to an inverter.

create extension if not exists timescaledb;

create table if not exists schema_migrations (
    version text primary key,
    applied_at timestamptz not null default now()
);

create table if not exists sites (
    site_id text primary key,
    name text,
    timezone text not null default 'Asia/Colombo',
    system_kw double precision not null,
    tilt_deg double precision,
    azimuth_deg double precision,
    latitude double precision,
    longitude double precision,
    location_id text
);

create table if not exists devices (
    device_id text primary key,
    site_id text not null references sites (site_id),
    token_hash text not null unique,
    created_at timestamptz not null default now()
);

create table if not exists readings (
    site_id text not null references sites (site_id),
    ts timestamptz not null,
    pv_kw double precision,
    consumption_kw double precision,
    import_kw double precision,
    export_kw double precision,
    data_label text not null default 'MEASURED',
    is_simulated boolean not null default false,
    primary key (site_id, ts)
);

select create_hypertable('readings', 'ts', if_not_exists => true);

create index if not exists readings_site_ts_idx on readings (site_id, ts desc);

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

create index if not exists forecast_runs_lookup_idx
    on forecast_runs (site_id, target, created_at desc);

create table if not exists forecasts (
    site_id text not null,
    target text not null,
    ts timestamptz not null,
    issued_at timestamptz not null,
    value_kw double precision not null,
    model_version text not null,
    run_id bigint references forecast_runs (run_id),
    data_label text not null default 'SIMULATED',
    is_simulated boolean not null default true,
    primary key (site_id, target, ts, issued_at)
);

select create_hypertable('forecasts', 'ts', if_not_exists => true);

create index if not exists forecasts_lookup_idx
    on forecasts (site_id, target, issued_at desc);
