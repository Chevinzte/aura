-- Preserve user-guided feature corrections as immutable overlays.

create table public.item_feature_corrections (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references public.users(id) on delete cascade,
    item_id uuid not null references public.items(id) on delete cascade,
    source_features_id uuid not null references public.item_visual_features(id) on delete restrict,
    version integer not null check (version > 0),
    is_active boolean not null default false,
    corrected_features jsonb not null check (jsonb_typeof(corrected_features) = 'object'),
    corrected_fields text[] not null check (cardinality(corrected_fields) > 0),
    canonical_embedding_text text not null,
    embedding vector(1536) not null,
    embedding_provider text not null,
    embedding_model text not null,
    embedding_dimensions integer not null check (embedding_dimensions = 1536),
    embedding_schema_version integer not null check (embedding_schema_version > 0),
    feature_schema_version integer not null check (feature_schema_version > 0),
    created_at timestamptz not null default now(),
    unique (item_id, version)
);

create unique index item_feature_corrections_one_active_per_item
    on public.item_feature_corrections (item_id)
    where is_active;
create index item_feature_corrections_user_created_at_idx
    on public.item_feature_corrections (user_id, created_at desc);

alter table public.aesthetic_profile_items
add column item_feature_correction_id uuid
references public.item_feature_corrections(id) on delete restrict;

alter table public.item_feature_corrections enable row level security;
revoke all on public.item_feature_corrections from anon, authenticated;

create function public.activate_item_feature_correction(
    p_correction_id uuid,
    p_user_id uuid,
    p_item_id uuid,
    p_source_features_id uuid,
    p_corrected_features jsonb,
    p_canonical_embedding_text text,
    p_embedding vector(1536),
    p_corrected_fields text[],
    p_embedding_provider text,
    p_embedding_model text,
    p_embedding_dimensions integer,
    p_embedding_schema_version integer,
    p_feature_schema_version integer
)
returns public.item_feature_corrections
language plpgsql
security definer
set search_path = ''
as $$
declare
    next_version integer;
    created_correction public.item_feature_corrections;
begin
    perform 1
    from public.items item
    join public.item_visual_features features
      on features.id = p_source_features_id
     and features.item_id = item.id
    where item.id = p_item_id
      and item.user_id = p_user_id
      and item.source = 'OWNED'
      and item.status = 'READY'
      and item.deleted_at is null
      and features.status = 'COMPLETED'
    for update of item;

    if not found then
        raise exception 'Owned wardrobe item is invalid';
    end if;

    select coalesce(max(version), 0) + 1
    into next_version
    from public.item_feature_corrections
    where item_id = p_item_id;

    update public.item_feature_corrections
    set is_active = false
    where item_id = p_item_id
      and is_active;

    insert into public.item_feature_corrections (
        id,
        user_id,
        item_id,
        source_features_id,
        version,
        is_active,
        corrected_features,
        corrected_fields,
        canonical_embedding_text,
        embedding,
        embedding_provider,
        embedding_model,
        embedding_dimensions,
        embedding_schema_version,
        feature_schema_version
    ) values (
        p_correction_id,
        p_user_id,
        p_item_id,
        p_source_features_id,
        next_version,
        true,
        p_corrected_features,
        p_corrected_fields,
        p_canonical_embedding_text,
        p_embedding,
        p_embedding_provider,
        p_embedding_model,
        p_embedding_dimensions,
        p_embedding_schema_version,
        p_feature_schema_version
    )
    returning * into created_correction;

    return created_correction;
end;
$$;

create function public.restore_item_feature_correction(
    p_user_id uuid,
    p_item_id uuid,
    p_failed_correction_id uuid,
    p_previous_correction_id uuid
)
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
    perform 1
    from public.items
    where id = p_item_id
      and user_id = p_user_id
    for update;

    if not found then
        raise exception 'Owned wardrobe item is invalid';
    end if;

    update public.item_feature_corrections
    set is_active = false
    where id = p_failed_correction_id
      and item_id = p_item_id
      and user_id = p_user_id;

    if p_previous_correction_id is not null then
        update public.item_feature_corrections
        set is_active = true
        where id = p_previous_correction_id
          and item_id = p_item_id
          and user_id = p_user_id;
    end if;
end;
$$;

create or replace function public.activate_aesthetic_profile(
    p_profile_id uuid,
    p_user_id uuid,
    p_profile_data jsonb,
    p_embedding_centroid vector(1536),
    p_colour_diversity double precision,
    p_style_diversity double precision,
    p_generated_summary text,
    p_profile_algorithm_version integer,
    p_feature_schema_version integer,
    p_embedding_model text,
    p_embedding_dimensions integer,
    p_embedding_schema_version integer,
    p_contributions jsonb
)
returns public.aesthetic_profiles
language plpgsql
security definer
set search_path = ''
as $$
declare
    contribution_count integer;
    valid_count integer;
    created_profile public.aesthetic_profiles;
begin
    perform 1 from public.users where id = p_user_id for update;
    if not found then raise exception 'AURA user does not exist'; end if;
    if jsonb_typeof(p_contributions) <> 'array' then
        raise exception 'Profile contributions must be an array';
    end if;

    contribution_count := jsonb_array_length(p_contributions);
    if contribution_count < 5 then
        raise exception 'At least five profile contributions are required';
    end if;

    select count(distinct contribution.feature_id)
    into valid_count
    from jsonb_to_recordset(p_contributions) as contribution(
        feature_id uuid,
        effective_weight double precision,
        correction_id uuid
    )
    join public.item_visual_features features on features.id = contribution.feature_id
    join public.items item on item.id = features.item_id
    left join public.item_feature_corrections correction
      on correction.id = contribution.correction_id
     and correction.item_id = item.id
     and correction.source_features_id = features.id
     and correction.user_id = p_user_id
     and correction.is_active
     and correction.embedding_model = p_embedding_model
     and correction.embedding_dimensions = p_embedding_dimensions
     and correction.embedding_schema_version = p_embedding_schema_version
     and correction.feature_schema_version = p_feature_schema_version
    where contribution.effective_weight > 0
      and item.user_id = p_user_id
      and item.source = 'OWNED'
      and item.status = 'READY'
      and item.deleted_at is null
      and features.status = 'COMPLETED'
      and features.feature_schema_version = p_feature_schema_version
      and features.embedding_model = p_embedding_model
      and features.embedding_dimensions = p_embedding_dimensions
      and features.embedding_schema_version = p_embedding_schema_version
      and (contribution.correction_id is null or correction.id is not null);

    if valid_count <> contribution_count then
        raise exception 'Profile contributions are invalid or incompatible';
    end if;

    update public.aesthetic_profiles set is_active = false
    where user_id = p_user_id and is_active;

    insert into public.aesthetic_profiles (
        id, user_id, is_active, profile_data, embedding_centroid,
        colour_diversity, style_diversity, generated_summary,
        contributing_item_count, profile_algorithm_version,
        feature_schema_version, embedding_model, embedding_dimensions,
        embedding_schema_version
    ) values (
        p_profile_id, p_user_id, true, p_profile_data, p_embedding_centroid,
        p_colour_diversity, p_style_diversity, p_generated_summary,
        contribution_count, p_profile_algorithm_version,
        p_feature_schema_version, p_embedding_model, p_embedding_dimensions,
        p_embedding_schema_version
    ) returning * into created_profile;

    insert into public.aesthetic_profile_items (
        profile_id, item_visual_features_id, item_feature_correction_id,
        effective_weight
    )
    select p_profile_id, contribution.feature_id, contribution.correction_id,
           contribution.effective_weight
    from jsonb_to_recordset(p_contributions) as contribution(
        feature_id uuid,
        effective_weight double precision,
        correction_id uuid
    );

    update public.users set onboarding_complete = true where id = p_user_id;
    return created_profile;
end;
$$;

revoke all on function public.activate_item_feature_correction(
    uuid, uuid, uuid, uuid, jsonb, text, vector, text[], text, text,
    integer, integer, integer
) from public, anon, authenticated;
grant execute on function public.activate_item_feature_correction(
    uuid, uuid, uuid, uuid, jsonb, text, vector, text[], text, text,
    integer, integer, integer
) to service_role;

revoke all on function public.restore_item_feature_correction(
    uuid, uuid, uuid, uuid
) from public, anon, authenticated;
grant execute on function public.restore_item_feature_correction(
    uuid, uuid, uuid, uuid
) to service_role;
