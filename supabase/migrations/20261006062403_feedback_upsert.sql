-- Upsert one feedback value per match and feedback category.

create function public.upsert_match_feedback(
    p_user_id uuid,
    p_match_analysis_id uuid,
    p_category public.feedback_category,
    p_feedback_type public.feedback_type,
    p_note text default null
)
returns public.feedback
language plpgsql
security definer
set search_path = ''
as $$
declare
    saved_feedback public.feedback;
begin
    if p_note is not null and char_length(p_note) > 500 then
        raise exception 'Feedback note exceeds 500 characters';
    end if;

    if not exists (
        select 1
        from public.match_analyses match
        where match.id = p_match_analysis_id
          and match.user_id = p_user_id
          and match.status = 'COMPLETED'
    ) then
        raise exception 'Completed match does not exist for this user';
    end if;

    insert into public.feedback (
        user_id,
        match_analysis_id,
        category,
        feedback_type,
        note
    ) values (
        p_user_id,
        p_match_analysis_id,
        p_category,
        p_feedback_type,
        p_note
    )
    on conflict (match_analysis_id, category)
    do update set
        feedback_type = excluded.feedback_type,
        note = excluded.note
    returning * into saved_feedback;

    return saved_feedback;
end;
$$;

revoke all on function public.upsert_match_feedback(
    uuid, uuid, public.feedback_category, public.feedback_type, text
) from public, anon, authenticated;

grant execute on function public.upsert_match_feedback(
    uuid, uuid, public.feedback_category, public.feedback_type, text
) to service_role;
