-- Store an optional, user-selected fashion presentation preference.

alter table public.users
add column fashion_presentation text;

alter table public.users
add constraint users_fashion_presentation_valid check (
    fashion_presentation is null
    or fashion_presentation in (
        'MENSWEAR',
        'WOMENSWEAR',
        'GENDER_NEUTRAL',
        'NO_PREFERENCE'
    )
);
