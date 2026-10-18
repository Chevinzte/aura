-- Store user-confirmed AI reanalysis as versioned feature revisions.

alter table public.item_feature_corrections
add column revision_kind text not null default 'USER_CORRECTION'
check (revision_kind in ('USER_CORRECTION', 'AI_REANALYSIS')),
add column accepted_at timestamptz default now();

update public.item_feature_corrections
set accepted_at = created_at
where revision_kind = 'USER_CORRECTION';

create index item_feature_corrections_pending_reanalysis_idx
    on public.item_feature_corrections (user_id, item_id, created_at desc)
    where revision_kind = 'AI_REANALYSIS' and accepted_at is null;

create function public.create_item_reanalysis_preview(
    p_revision_id uuid,
    p_user_id uuid,
    p_item_id uuid,
    p_source_features_id uuid,
    p_features jsonb,
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
    created_revision public.item_feature_corrections;
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

    delete from public.item_feature_corrections
    where user_id = p_user_id
      and item_id = p_item_id
      and revision_kind = 'AI_REANALYSIS'
      and accepted_at is null
      and not is_active;

    select coalesce(max(version), 0) + 1
    into next_version
    from public.item_feature_corrections
    where item_id = p_item_id;

    insert into public.item_feature_corrections (
        id, user_id, item_id, source_features_id, version, is_active,
        corrected_features, corrected_fields, canonical_embedding_text,
        embedding, embedding_provider, embedding_model, embedding_dimensions,
        embedding_schema_version, feature_schema_version, revision_kind,
        accepted_at
    ) values (
        p_revision_id, p_user_id, p_item_id, p_source_features_id,
        next_version, false, p_features, p_corrected_fields,
        p_canonical_embedding_text, p_embedding, p_embedding_provider,
        p_embedding_model, p_embedding_dimensions, p_embedding_schema_version,
        p_feature_schema_version, 'AI_REANALYSIS', null
    )
    returning * into created_revision;

    return created_revision;
end;
$$;

create function public.activate_item_reanalysis(
    p_user_id uuid,
    p_item_id uuid,
    p_revision_id uuid
)
returns public.item_feature_corrections
language plpgsql
security definer
set search_path = ''
as $$
declare
    activated_revision public.item_feature_corrections;
begin
    perform 1
    from public.items
    where id = p_item_id
      and user_id = p_user_id
      and source = 'OWNED'
      and status = 'READY'
      and deleted_at is null
    for update;

    if not found then
        raise exception 'Owned wardrobe item is invalid';
    end if;

    perform 1
    from public.item_feature_corrections
    where id = p_revision_id
      and user_id = p_user_id
      and item_id = p_item_id
      and revision_kind = 'AI_REANALYSIS'
      and accepted_at is null
      and not is_active;

    if not found then
        raise exception 'Reanalysis preview is invalid or expired';
    end if;

    update public.item_feature_corrections
    set is_active = false
    where item_id = p_item_id
      and is_active;

    update public.item_feature_corrections
    set is_active = true,
        accepted_at = now()
    where id = p_revision_id
    returning * into activated_revision;

    return activated_revision;
end;
$$;

create function public.discard_item_reanalysis(
    p_user_id uuid,
    p_item_id uuid,
    p_revision_id uuid
)
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
    delete from public.item_feature_corrections
    where id = p_revision_id
      and user_id = p_user_id
      and item_id = p_item_id
      and revision_kind = 'AI_REANALYSIS'
      and accepted_at is null
      and not is_active;
end;
$$;

revoke all on function public.create_item_reanalysis_preview(
    uuid, uuid, uuid, uuid, jsonb, text, vector, text[], text, text,
    integer, integer, integer
) from public, anon, authenticated;
grant execute on function public.create_item_reanalysis_preview(
    uuid, uuid, uuid, uuid, jsonb, text, vector, text[], text, text,
    integer, integer, integer
) to service_role;

revoke all on function public.activate_item_reanalysis(uuid, uuid, uuid)
from public, anon, authenticated;
grant execute on function public.activate_item_reanalysis(uuid, uuid, uuid)
to service_role;

revoke all on function public.discard_item_reanalysis(uuid, uuid, uuid)
from public, anon, authenticated;
grant execute on function public.discard_item_reanalysis(uuid, uuid, uuid)
to service_role;
