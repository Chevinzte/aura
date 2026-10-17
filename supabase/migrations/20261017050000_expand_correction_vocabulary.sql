-- Promote existing compatible representations to the additive vocabulary revision.
-- Canonical field order and the embedding model are unchanged, so no image
-- reanalysis or embedding regeneration is required for existing records.

update public.item_visual_features
set feature_schema_version = 2,
    embedding_schema_version = 2,
    updated_at = now()
where feature_schema_version = 1
  and embedding_schema_version = 1;

update public.item_feature_corrections
set feature_schema_version = 2,
    embedding_schema_version = 2
where feature_schema_version = 1
  and embedding_schema_version = 1;

update public.aesthetic_profiles
set feature_schema_version = 2,
    embedding_schema_version = 2,
    profile_data = jsonb_set(
        profile_data,
        '{embeddingCentroid,schema_version}',
        '2'::jsonb,
        false
    )
where feature_schema_version = 1
  and embedding_schema_version = 1;
