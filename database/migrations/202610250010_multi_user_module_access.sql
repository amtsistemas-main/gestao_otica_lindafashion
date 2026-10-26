-- Multilogin: o dono/administrador cria os logins (Edge Function admin-users) e escolhe
-- quais módulos cada usuário vê. allowed_modules nulo = todos os módulos; donos e
-- administradores sempre acessam tudo.

alter table public.organization_members
    add column if not exists email text not null default '',
    add column if not exists allowed_modules text[];

alter table public.organization_members drop constraint if exists organization_members_allowed_modules_check;
alter table public.organization_members add constraint organization_members_allowed_modules_check check (
    allowed_modules is null or allowed_modules <@ array[
        'vendas', 'clientes', 'relacionamento', 'produtos', 'estoque', 'fornecedores',
        'financeiro', 'indicadores', 'analises', 'configuracoes'
    ]::text[]
);

comment on column public.organization_members.allowed_modules is
'Módulos visíveis para o usuário (nulo = todos). Ignorado para owner/admin.';
comment on column public.organization_members.email is
'E-mail do login, gravado pela Edge Function admin-users para exibição à equipe.';

-- O aplicativo continua podendo alterar apenas o nome de exibição (papel, módulos e
-- situação são alterados somente pela Edge Function, com a chave do servidor).
revoke update on public.organization_members from authenticated;
grant update (display_name) on public.organization_members to authenticated;

create or replace function public.has_module_access(p_org uuid, p_module text)
returns boolean
language sql
stable
security definer
set search_path = public, pg_temp
as $$
    select exists (
        select 1 from public.organization_members
        where organization_id = p_org and user_id = auth.uid() and active = true
          and (role in ('owner', 'admin') or allowed_modules is null or p_module = any(allowed_modules))
    );
$$;

revoke all on function public.has_module_access(uuid, text) from public, anon;
grant execute on function public.has_module_access(uuid, text) to authenticated;

-- Financeiro: leitura para quem tem Financeiro ou Indicadores; escrita só com Financeiro.
-- As vendas continuam lançando no financeiro pela função transacional do PDV.
drop policy if exists finance_select_organization_members on public.financial_entries;
create policy finance_select_organization_members on public.financial_entries for select to authenticated
using (public.has_module_access(organization_id, 'financeiro') or public.has_module_access(organization_id, 'indicadores'));

drop policy if exists finance_insert_organization_members on public.financial_entries;
create policy finance_insert_organization_members on public.financial_entries for insert to authenticated
with check (
    (created_by is null or created_by = (select auth.uid()))
    and public.has_module_access(organization_id, 'financeiro')
);

drop policy if exists finance_update_organization_members on public.financial_entries;
create policy finance_update_organization_members on public.financial_entries for update to authenticated
using (public.has_module_access(organization_id, 'financeiro'))
with check (public.has_module_access(organization_id, 'financeiro'));
