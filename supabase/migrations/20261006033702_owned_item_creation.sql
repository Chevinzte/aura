-- Create an item and its versioned pending feature analysis atomically.

create function public.create_item_with_analysis(
    p_item_id uuid,
    p_user_id uuid,
    p_source public.item_source,
    p_storage_path text,
    p_original_filename text,
    p_mime_type text,
    p_size_bytes bigint,
    p_width_px integer,
    p_height_px integer,
    p_content_sha256 text,
    p_item_name text,
    p_vision_provider text,
    p_vision_model text,
    p_vision_prompt_version integer,
    p_feature_schema_version integer,
    p_embedding_provider text,
    p_embedding_model text,
    p_embedding_dimensions integer,
    p_embedding_schema_version integer
)
returns table(item_id uuid, analysis_id uuid)
language plpgsql
security definer
set search_path = ''
as $$
declare
    created_analysis_id uuid;
begin
    insert into public.items (
        id, user_id, source, storage_path, original_filename, mime_type,
        size_bytes, width_px, height_px, content_sha256, item_name
    ) values (
        p_item_id, p_user_id, p_source, p_storage_path, p_original_filename,
        p_mime_type, p_size_bytes, p_width_px, p_height_px, p_content_sha256,
        p_item_name
    );

    insert into public.item_visual_features (
        item_id, status, vision_provider, vision_model, vision_prompt_version,
        feature_schema_version, embedding_provider, embedding_model,
        embedding_dimensions, embedding_schema_version
    ) values (
        p_item_id, 'PENDING', p_vision_provider, p_vision_model,
        p_vision_prompt_version, p_feature_schema_version, p_embedding_provider,
        p_embedding_model, p_embedding_dimensions, p_embedding_schema_version
    )
    returning id into created_analysis_id;

    return query select p_item_id, created_analysis_id;
end;
$$;

revoke all on function public.create_item_with_analysis(
    uuid, uuid, public.item_source, text, text, text, bigint, integer, integer,
    text, text, text, text, integer, integer, text, text, integer, integer
) from public, anon, authenticated;

grant execute on function public.create_item_with_analysis(
    uuid, uuid, public.item_source, text, text, text, bigint, integer, integer,
    text, text, text, text, integer, integer, text, text, integer, integer
) to service_role;
