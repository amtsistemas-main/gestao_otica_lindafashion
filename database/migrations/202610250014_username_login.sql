-- Sistema fechado com login por nome de usuário.
-- O Supabase Auth exige e-mail: cada login usa o e-mail interno <usuario>@usuarios.local,
-- que ninguém digita e que nunca recebe mensagens. Os logins são criados somente pelo
-- dono/administrador (Edge Function admin-users); o cadastro público fica desativado.

alter table public.organization_members add column if not exists username text not null default '';

alter table public.organization_members drop constraint if exists organization_members_username_format_check;
alter table public.organization_members add constraint organization_members_username_format_check
    check (username = '' or username ~ '^[a-z0-9][a-z0-9._-]{2,31}$');

-- Único no projeto inteiro (o e-mail interno também é único no Auth).
create unique index if not exists organization_members_username_uidx
    on public.organization_members (username) where username <> '';

-- Logins já existentes ganham o nome de usuário a partir do e-mail interno.
update public.organization_members
set username = split_part(email, '@', 1)
where username = '' and email like '%@usuarios.local'
  and split_part(email, '@', 1) ~ '^[a-z0-9][a-z0-9._-]{2,31}$';

comment on column public.organization_members.username is
'Nome de usuário do login (e-mail interno <username>@usuarios.local no Supabase Auth).';
