-- Keep item and feature-analysis lifecycle state changes atomic.

create function public.start_item_feature_analysis(p_analysis_id uuid)
returns public.item_visual_features
language plpgsql
security definer
set search_path = ''
as $$
declare
    updated_analysis public.item_visual_features;
begin
    update public.item_visual_features
    set
        status = 'PROCESSING',
        attempt_count = attempt_count + 1,
        started_at = now(),
        completed_at = null,
        error_code = null,
        error_detail = null
    where id = p_analysis_id
      and status in ('PENDING', 'FAILED')
    returning * into updated_analysis;

    if updated_analysis.id is null then
        raise exception 'Feature analysis is not available to start';
    end if;

    update public.items
    set status = 'ANALYZING'
    where id = updated_analysis.item_id;

    return updated_analysis;
end;
$$;

create function public.complete_item_feature_analysis(
    p_analysis_id uuid,
    p_features jsonb,
    p_canonical_embedding_text text,
    p_embedding vector(1536)
)
returns public.item_visual_features
language plpgsql
security definer
set search_path = ''
as $$
declare
    updated_analysis public.item_visual_features;
begin
    update public.item_visual_features
    set
        status = 'COMPLETED',
        features = p_features,
        canonical_embedding_text = p_canonical_embedding_text,
        embedding = p_embedding,
        completed_at = now(),
        error_code = null,
        error_detail = null
    where id = p_analysis_id
      and status = 'PROCESSING'
    returning * into updated_analysis;

    if updated_analysis.id is null then
        raise exception 'Feature analysis is not processing';
    end if;

    update public.items
    set status = 'READY'
    where id = updated_analysis.item_id;

    return updated_analysis;
end;
$$;

create function public.fail_item_feature_analysis(
    p_analysis_id uuid,
    p_error_code text,
    p_error_detail text default null
)
returns public.item_visual_features
language plpgsql
security definer
set search_path = ''
as $$
declare
    updated_analysis public.item_visual_features;
begin
    if nullif(trim(p_error_code), '') is null then
        raise exception 'Error code is required';
    end if;

    update public.item_visual_features
    set
        status = 'FAILED',
        completed_at = now(),
        error_code = p_error_code,
        error_detail = p_error_detail
    where id = p_analysis_id
      and status in ('PENDING', 'PROCESSING', 'FAILED')
    returning * into updated_analysis;

    if updated_analysis.id is null then
        raise exception 'Feature analysis cannot be failed';
    end if;

    update public.items
    set status = 'FAILED'
    where id = updated_analysis.item_id;

    return updated_analysis;
end;
$$;

revoke all on function public.start_item_feature_analysis(uuid)
    from public, anon, authenticated;
revoke all on function public.complete_item_feature_analysis(uuid, jsonb, text, vector)
    from public, anon, authenticated;
revoke all on function public.fail_item_feature_analysis(uuid, text, text)
    from public, anon, authenticated;

grant execute on function public.start_item_feature_analysis(uuid) to service_role;
grant execute on function public.complete_item_feature_analysis(uuid, jsonb, text, vector)
    to service_role;
grant execute on function public.fail_item_feature_analysis(uuid, text, text) to service_role;
