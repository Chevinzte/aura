-- Safely remove owned items and deactivate profiles before deterministic rebuilds.

create function public.remove_owned_profile_item(
    p_user_id uuid,
    p_item_id uuid
)
returns table(item_id uuid)
language plpgsql
security definer
set search_path = ''
as $$
begin
    perform 1
    from public.users
    where id = p_user_id
    for update;

    if not found then
        raise exception 'AURA user does not exist';
    end if;

    return query
    update public.items as item
    set deleted_at = now()
    where item.id = p_item_id
      and item.user_id = p_user_id
      and item.source = 'OWNED'
      and item.deleted_at is null
    returning item.id;

    if not found then
        raise exception 'Owned item does not exist';
    end if;

    update public.aesthetic_profiles
    set is_active = false
    where user_id = p_user_id
      and is_active;

    update public.users
    set onboarding_complete = false
    where id = p_user_id;
end;
$$;

revoke all on function public.remove_owned_profile_item(uuid, uuid)
from public, anon, authenticated;
grant execute on function public.remove_owned_profile_item(uuid, uuid)
to service_role;

create function public.reset_owned_profile_items(p_user_id uuid)
returns table(item_id uuid)
language plpgsql
security definer
set search_path = ''
as $$
begin
    perform 1
    from public.users
    where id = p_user_id
    for update;

    if not found then
        raise exception 'AURA user does not exist';
    end if;

    return query
    update public.items as item
    set deleted_at = now()
    where item.user_id = p_user_id
      and item.source = 'OWNED'
      and item.deleted_at is null
    returning item.id;

    update public.aesthetic_profiles
    set is_active = false
    where user_id = p_user_id
      and is_active;

    update public.users
    set onboarding_complete = false
    where id = p_user_id;
end;
$$;

revoke all on function public.reset_owned_profile_items(uuid)
from public, anon, authenticated;
grant execute on function public.reset_owned_profile_items(uuid)
to service_role;
