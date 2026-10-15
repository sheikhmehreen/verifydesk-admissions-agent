-- Run this SQL in the Supabase SQL Editor for the VerifyDesk project.
-- Use only synthetic demo documents. Keep the documents bucket private.

create extension if not exists pgcrypto;

create table if not exists public.applications (
    id uuid primary key default gen_random_uuid(),
    outcome text not null check (outcome in ('PASS', 'FAIL', 'NEEDS_REVIEW')),
    review_required boolean not null default false,
    created_at timestamptz not null default now()
);

create table if not exists public.documents (
    id uuid primary key default gen_random_uuid(),
    application_id uuid not null references public.applications(id) on delete cascade,
    doc_type text not null check (doc_type in ('id_card', 'transcript', 'degree')),
    file_path text not null,
    read_status text not null,
    extract_status text,
    needs_review boolean not null default false,
    created_at timestamptz not null default now(),
    unique (application_id, doc_type)
);

create table if not exists public.extractions (
    id uuid primary key default gen_random_uuid(),
    document_id uuid not null unique references public.documents(id) on delete cascade,
    fields jsonb not null default '{}'::jsonb,
    evidence jsonb not null default '{}'::jsonb,
    detail text not null default '',
    created_at timestamptz not null default now()
);

create table if not exists public.results (
    id uuid primary key default gen_random_uuid(),
    application_id uuid not null unique references public.applications(id) on delete cascade,
    outcome text not null check (outcome in ('PASS', 'FAIL', 'NEEDS_REVIEW')),
    reasons jsonb not null default '[]'::jsonb,
    review_required boolean not null default false,
    rule_version text not null,
    created_at timestamptz not null default now()
);

alter table public.applications enable row level security;
alter table public.documents enable row level security;
alter table public.extractions enable row level security;
alter table public.results enable row level security;

-- The server-side secret key bypasses RLS. Never expose it to browser/client code.
-- Create a private Storage bucket named "documents" in Storage settings if it doesn't exist.
