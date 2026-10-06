-- Atomically replace a user's active aesthetic profile snapshot.

create function public.activate_aesthetic_profile(
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
    perform 1
    from public.users
    where id = p_user_id
    for update;

    if not found then
        raise exception 'AURA user does not exist';
    end if;

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
        effective_weight double precision
    )
    join public.item_visual_features features
      on features.id = contribution.feature_id
    join public.items item
      on item.id = features.item_id
    where contribution.effective_weight > 0
      and item.user_id = p_user_id
      and item.source = 'OWNED'
      and item.status = 'READY'
      and item.deleted_at is null
      and features.status = 'COMPLETED'
      and features.feature_schema_version = p_feature_schema_version
      and features.embedding_model = p_embedding_model
      and features.embedding_dimensions = p_embedding_dimensions
      and features.embedding_schema_version = p_embedding_schema_version;

    if valid_count <> contribution_count then
        raise exception 'Profile contributions are invalid or incompatible';
    end if;

    update public.aesthetic_profiles
    set is_active = false
    where user_id = p_user_id
      and is_active;

    insert into public.aesthetic_profiles (
        id,
        user_id,
        is_active,
        profile_data,
        embedding_centroid,
        colour_diversity,
        style_diversity,
        generated_summary,
        contributing_item_count,
        profile_algorithm_version,
        feature_schema_version,
        embedding_model,
        embedding_dimensions,
        embedding_schema_version
    ) values (
        p_profile_id,
        p_user_id,
        true,
        p_profile_data,
        p_embedding_centroid,
        p_colour_diversity,
        p_style_diversity,
        p_generated_summary,
        contribution_count,
        p_profile_algorithm_version,
        p_feature_schema_version,
        p_embedding_model,
        p_embedding_dimensions,
        p_embedding_schema_version
    )
    returning * into created_profile;

    insert into public.aesthetic_profile_items (
        profile_id,
        item_visual_features_id,
        effective_weight
    )
    select
        p_profile_id,
        contribution.feature_id,
        contribution.effective_weight
    from jsonb_to_recordset(p_contributions) as contribution(
        feature_id uuid,
        effective_weight double precision
    );

    update public.users
    set onboarding_complete = true
    where id = p_user_id;

    return created_profile;
end;
$$;

revoke all on function public.activate_aesthetic_profile(
    uuid, uuid, jsonb, vector, double precision, double precision, text,
    integer, integer, text, integer, integer, jsonb
) from public, anon, authenticated;

grant execute on function public.activate_aesthetic_profile(
    uuid, uuid, jsonb, vector, double precision, double precision, text,
    integer, integer, text, integer, integer, jsonb
) to service_role;
