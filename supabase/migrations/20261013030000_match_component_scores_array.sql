-- Match component scores are an ordered list in the V1 domain contract.

alter table public.match_analyses
drop constraint match_analyses_component_scores_object;

alter table public.match_analyses
add constraint match_analyses_component_scores_array check (
    component_scores is null or jsonb_typeof(component_scores) = 'array'
);
