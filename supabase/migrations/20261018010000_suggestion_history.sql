-- Persist generated concept metadata so suggestions can avoid recent repetition.
-- Generated images and prompts remain transient and are not stored.

create table public.suggestion_history (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references public.users(id) on delete cascade,
    intent text not null check (
        intent in ('SAFE_EXTENSION', 'INTENTIONAL_CONTRAST', 'SURPRISE_ME')
    ),
    category text not null check (
        category in ('ANY', 'TOPS', 'OUTERWEAR', 'PANTS', 'ACCESSORIES', 'FOOTWEAR')
    ),
    label text not null check (length(trim(label)) between 1 and 120),
    item_type text not null check (length(trim(item_type)) between 1 and 120),
    created_at timestamptz not null default now()
);

create index suggestion_history_user_created_at_idx
    on public.suggestion_history (user_id, created_at desc);

alter table public.suggestion_history enable row level security;

revoke all on public.suggestion_history from anon, authenticated;
