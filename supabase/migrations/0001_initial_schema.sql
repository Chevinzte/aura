-- AURA MVP initial database schema.
-- This migration implements docs/DATABASE_SCHEMA.md.

create extension if not exists pgcrypto;
create extension if not exists vector;

create type public.item_source as enum ('OWNED', 'CANDIDATE');
create type public.item_status as enum ('UPLOADED', 'ANALYZING', 'READY', 'FAILED');
create type public.analysis_status as enum ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED');
create type public.match_classification as enum (
    'STRONG_FIT',
    'MODERATE_FIT',
    'INTENTIONAL_CONTRAST',
    'WEAK_FIT',
    'UNCERTAIN'
);
create type public.feedback_category as enum ('TASTE', 'DECISION');
create type public.feedback_type as enum ('LIKE', 'DISLIKE', 'BOUGHT', 'NOT_BOUGHT');

create function public.set_updated_at()
returns trigger
language plpgsql
set search_path = public
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

create table public.users (
    id uuid primary key default gen_random_uuid(),
    telegram_user_id bigint not null unique,
    display_name text,
    onboarding_complete boolean not null default false,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table public.items (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references public.users(id) on delete cascade,
    source public.item_source not null,
    status public.item_status not null default 'UPLOADED',
    storage_bucket text not null default 'item-images',
    storage_path text not null unique,
    original_filename text,
    mime_type text not null,
    size_bytes bigint not null check (size_bytes > 0),
    width_px integer check (width_px is null or width_px > 0),
    height_px integer check (height_px is null or height_px > 0),
    content_sha256 text not null check (content_sha256 ~ '^[0-9a-f]{64}$'),
    item_name text,
    deleted_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table public.item_visual_features (
    id uuid primary key default gen_random_uuid(),
    item_id uuid not null references public.items(id) on delete cascade,
    status public.analysis_status not null default 'PENDING',
    features jsonb,
    canonical_embedding_text text,
    embedding vector(1536),
    vision_provider text not null,
    vision_model text not null,
    vision_prompt_version integer not null check (vision_prompt_version > 0),
    feature_schema_version integer not null check (feature_schema_version > 0),
    embedding_provider text not null,
    embedding_model text not null,
    embedding_dimensions integer not null check (embedding_dimensions = 1536),
    embedding_schema_version integer not null check (embedding_schema_version > 0),
    attempt_count smallint not null default 0 check (attempt_count >= 0),
    error_code text,
    error_detail text,
    started_at timestamptz,
    completed_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint item_visual_features_features_object check (
        features is null or jsonb_typeof(features) = 'object'
    ),
    constraint item_visual_features_completed_data check (
        status <> 'COMPLETED'
        or (
            features is not null
            and canonical_embedding_text is not null
            and embedding is not null
            and completed_at is not null
        )
    ),
    constraint item_visual_features_failed_error check (
        status <> 'FAILED' or (error_code is not null and completed_at is not null)
    ),
    unique (
        item_id,
        vision_provider,
        vision_model,
        vision_prompt_version,
        feature_schema_version,
        embedding_provider,
        embedding_model,
        embedding_dimensions,
        embedding_schema_version
    )
);

create table public.aesthetic_profiles (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references public.users(id) on delete cascade,
    is_active boolean not null default false,
    profile_data jsonb not null check (jsonb_typeof(profile_data) = 'object'),
    embedding_centroid vector(1536) not null,
    colour_diversity double precision not null check (colour_diversity between 0 and 1),
    style_diversity double precision not null check (style_diversity between 0 and 1),
    generated_summary text not null,
    contributing_item_count integer not null check (contributing_item_count >= 5),
    profile_algorithm_version integer not null check (profile_algorithm_version > 0),
    feature_schema_version integer not null check (feature_schema_version > 0),
    embedding_model text not null,
    embedding_dimensions integer not null check (embedding_dimensions = 1536),
    embedding_schema_version integer not null check (embedding_schema_version > 0),
    created_at timestamptz not null default now()
);

create table public.aesthetic_profile_items (
    profile_id uuid not null references public.aesthetic_profiles(id) on delete cascade,
    item_visual_features_id uuid not null references public.item_visual_features(id) on delete cascade,
    effective_weight double precision not null check (effective_weight > 0),
    created_at timestamptz not null default now(),
    primary key (profile_id, item_visual_features_id)
);

create table public.match_analyses (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references public.users(id) on delete cascade,
    candidate_item_id uuid not null references public.items(id) on delete cascade,
    candidate_features_id uuid not null references public.item_visual_features(id) on delete restrict,
    profile_id uuid not null references public.aesthetic_profiles(id) on delete restrict,
    status public.analysis_status not null default 'PENDING',
    overall_score double precision check (overall_score is null or overall_score between 0 and 1),
    classification public.match_classification,
    component_scores jsonb,
    matching_evidence jsonb,
    contrasting_evidence jsonb,
    explanation text,
    scoring_version integer not null check (scoring_version > 0),
    explanation_version integer not null check (explanation_version > 0),
    error_code text,
    error_detail text,
    started_at timestamptz,
    completed_at timestamptz,
    created_at timestamptz not null default now(),
    constraint match_analyses_component_scores_object check (
        component_scores is null or jsonb_typeof(component_scores) = 'object'
    ),
    constraint match_analyses_matching_evidence_array check (
        matching_evidence is null or jsonb_typeof(matching_evidence) = 'array'
    ),
    constraint match_analyses_contrasting_evidence_array check (
        contrasting_evidence is null or jsonb_typeof(contrasting_evidence) = 'array'
    ),
    constraint match_analyses_completed_data check (
        status <> 'COMPLETED'
        or (
            overall_score is not null
            and classification is not null
            and component_scores is not null
            and matching_evidence is not null
            and contrasting_evidence is not null
            and explanation is not null
            and completed_at is not null
        )
    ),
    constraint match_analyses_failed_error check (
        status <> 'FAILED' or (error_code is not null and completed_at is not null)
    ),
    unique (candidate_features_id, profile_id, scoring_version, explanation_version)
);

create table public.feedback (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references public.users(id) on delete cascade,
    match_analysis_id uuid not null references public.match_analyses(id) on delete cascade,
    category public.feedback_category not null,
    feedback_type public.feedback_type not null,
    note text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint feedback_type_matches_category check (
        (category = 'TASTE' and feedback_type in ('LIKE', 'DISLIKE'))
        or (category = 'DECISION' and feedback_type in ('BOUGHT', 'NOT_BOUGHT'))
    ),
    unique (match_analysis_id, category)
);

create unique index aesthetic_profiles_one_active_per_user
    on public.aesthetic_profiles (user_id)
    where is_active;

create index items_active_user_created_at_idx
    on public.items (user_id, created_at desc)
    where deleted_at is null;
create index items_active_user_source_status_idx
    on public.items (user_id, source, status)
    where deleted_at is null;
create index items_user_content_sha256_idx
    on public.items (user_id, content_sha256);
create index item_visual_features_item_created_at_idx
    on public.item_visual_features (item_id, created_at desc);
create index item_visual_features_status_created_at_idx
    on public.item_visual_features (status, created_at);
create index aesthetic_profiles_user_created_at_idx
    on public.aesthetic_profiles (user_id, created_at desc);
create index aesthetic_profile_items_features_idx
    on public.aesthetic_profile_items (item_visual_features_id);
create index match_analyses_user_created_at_idx
    on public.match_analyses (user_id, created_at desc);
create index match_analyses_candidate_item_created_at_idx
    on public.match_analyses (candidate_item_id, created_at desc);
create index match_analyses_status_created_at_idx
    on public.match_analyses (status, created_at);
create index feedback_user_created_at_idx
    on public.feedback (user_id, created_at desc);

create trigger users_set_updated_at
before update on public.users
for each row execute function public.set_updated_at();

create trigger items_set_updated_at
before update on public.items
for each row execute function public.set_updated_at();

create trigger item_visual_features_set_updated_at
before update on public.item_visual_features
for each row execute function public.set_updated_at();

create trigger feedback_set_updated_at
before update on public.feedback
for each row execute function public.set_updated_at();

alter table public.users enable row level security;
alter table public.items enable row level security;
alter table public.item_visual_features enable row level security;
alter table public.aesthetic_profiles enable row level security;
alter table public.aesthetic_profile_items enable row level security;
alter table public.match_analyses enable row level security;
alter table public.feedback enable row level security;

revoke all on public.users from anon, authenticated;
revoke all on public.items from anon, authenticated;
revoke all on public.item_visual_features from anon, authenticated;
revoke all on public.aesthetic_profiles from anon, authenticated;
revoke all on public.aesthetic_profile_items from anon, authenticated;
revoke all on public.match_analyses from anon, authenticated;
revoke all on public.feedback from anon, authenticated;

insert into storage.buckets (id, name, public)
values ('item-images', 'item-images', false)
on conflict (id) do update set public = false;
