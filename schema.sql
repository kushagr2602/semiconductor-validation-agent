-- Synthetic chip-validation schema.
-- Mirrors the shape of a real semiconductor validation database, but every
-- row inserted by seed_data.py is fabricated for this demo project.

create table if not exists chip_specs (
    id serial primary key,
    chip_name text not null,
    target_market text not null,        -- e.g. 'automotive', 'industrial', 'edge-ai'
    package_type text not null,         -- e.g. 'QFN-48', 'BGA-256'
    created_at timestamptz not null default now()
);

create table if not exists test_requirements (
    id serial primary key,
    chip_id integer not null references chip_specs(id),
    requirement_text text not null,
    category text not null,             -- 'thermal' | 'electrical' | 'timing' | 'emc'
    priority text not null default 'medium',  -- 'low' | 'medium' | 'high' | 'critical'
    created_at timestamptz not null default now()
);

create table if not exists test_cases (
    id serial primary key,
    requirement_id integer not null references test_requirements(id),
    title text not null,
    steps jsonb not null,               -- ordered list of step strings
    expected_result text not null,
    generated_by_llm boolean not null default false,
    created_at timestamptz not null default now()
);

create table if not exists test_runs (
    id serial primary key,
    test_case_id integer not null references test_cases(id),
    run_at timestamptz not null default now(),
    status text not null,               -- 'pass' | 'fail' | 'blocked'
    measured_value text,
    notes text
);

create index if not exists idx_test_requirements_chip on test_requirements(chip_id);
create index if not exists idx_test_cases_requirement on test_cases(requirement_id);
create index if not exists idx_test_runs_case on test_runs(test_case_id);
create index if not exists idx_test_runs_status on test_runs(status);
