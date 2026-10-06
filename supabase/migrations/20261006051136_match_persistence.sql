-- Validate ownership and record one immutable, idempotent match result.

create function public.record_completed_match(
    p_match_id uuid,
    p_user_id uuid,
    p_candidate_item_id uuid,
    p_candidate_features_id uuid,
    p_profile_id uuid,
    p_overall_score double precision,
    p_classification public.match_classification,
    p_component_scores jsonb,
    p_matching_evidence jsonb,
    p_contrasting_evidence jsonb,
    p_explanation text,
    p_scoring_version integer,
    p_explanation_version integer
)
returns public.match_analyses
language plpgsql
security definer
set search_path = ''
as $$
declare
    saved_match public.match_analyses;
begin
    if not exists (
        select 1
        from public.items item
        join public.item_visual_features features
          on features.item_id = item.id
        where item.id = p_candidate_item_id
          and item.user_id = p_user_id
          and item.source = 'CANDIDATE'
          and item.status = 'READY'
          and item.deleted_at is null
          and features.id = p_candidate_features_id
          and features.status = 'COMPLETED'
    ) then
        raise exception 'Candidate item or feature analysis is invalid';
    end if;

    if not exists (
        select 1
        from public.aesthetic_profiles profile
        where profile.id = p_profile_id
          and profile.user_id = p_user_id
    ) then
        raise exception 'Aesthetic profile is invalid';
    end if;

    insert into public.match_analyses (
        id,
        user_id,
        candidate_item_id,
        candidate_features_id,
        profile_id,
        status,
        overall_score,
        classification,
        component_scores,
        matching_evidence,
        contrasting_evidence,
        explanation,
        scoring_version,
        explanation_version,
        completed_at
    ) values (
        p_match_id,
        p_user_id,
        p_candidate_item_id,
        p_candidate_features_id,
        p_profile_id,
        'COMPLETED',
        p_overall_score,
        p_classification,
        p_component_scores,
        p_matching_evidence,
        p_contrasting_evidence,
        p_explanation,
        p_scoring_version,
        p_explanation_version,
        now()
    )
    on conflict (
        candidate_features_id,
        profile_id,
        scoring_version,
        explanation_version
    ) do nothing
    returning * into saved_match;

    if saved_match.id is null then
        select *
        into saved_match
        from public.match_analyses
        where candidate_features_id = p_candidate_features_id
          and profile_id = p_profile_id
          and scoring_version = p_scoring_version
          and explanation_version = p_explanation_version;
    end if;

    return saved_match;
end;
$$;

revoke all on function public.record_completed_match(
    uuid, uuid, uuid, uuid, uuid, double precision,
    public.match_classification, jsonb, jsonb, jsonb, text, integer, integer
) from public, anon, authenticated;

grant execute on function public.record_completed_match(
    uuid, uuid, uuid, uuid, uuid, double precision,
    public.match_classification, jsonb, jsonb, jsonb, text, integer, integer
) to service_role;
