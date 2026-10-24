-- Customer registry and CRM foundation.
-- All records are isolated by organization and protected by RLS.
create table if not exists public.customers (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null references public.organizations(id) on delete cascade,
    full_name text not null check (length(trim(full_name)) > 0),
    document text not null default '',
    email text not null default '',
    phone text not null default '',
    whatsapp text not null default '',
    birth_date date,
    postal_code text not null default '',
    street text not null default '',
    address_number text not null default '',
    address_complement text not null default '',
    neighborhood text not null default '',
    city text not null default '',
    state text not null default '',
    notes text not null default '',
    marketing_email_consent boolean not null default false,
    whatsapp_consent boolean not null default false,
    active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (id, organization_id)
);
create index if not exists customers_org_name_idx on public.customers (organization_id, full_name);
create index if not exists customers_org_email_idx on public.customers (organization_id, lower(email)) where email <> '';
create index if not exists customers_org_phone_idx on public.customers (organization_id, phone) where phone <> '';

create table if not exists public.customer_interactions (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null references public.organizations(id) on delete cascade,
    customer_id uuid not null,
    interaction_type text not null default 'observacao'
        check (interaction_type in ('observacao','ligacao','email','whatsapp','follow_up','status_pedido')),
    subject text not null default '',
    body text not null default '',
    order_status text not null default ''
        check (order_status in ('','em_desenvolvimento','pronto','entregue','cancelado')),
    follow_up_at timestamptz,
    created_by uuid references auth.users(id) on delete set null,
    created_at timestamptz not null default now(),
    constraint customer_interactions_customer_org_fk
        foreign key (customer_id, organization_id)
        references public.customers (id, organization_id) on delete cascade
);
create index if not exists customer_interactions_org_customer_created_idx
    on public.customer_interactions (organization_id, customer_id, created_at desc);
create index if not exists customer_interactions_follow_up_idx
    on public.customer_interactions (organization_id, follow_up_at)
    where follow_up_at is not null;

alter table public.customers enable row level security;
alter table public.customer_interactions enable row level security;

drop policy if exists customers_select_org_member on public.customers;
create policy customers_select_org_member on public.customers for select to authenticated
using (exists (select 1 from public.organization_members om where om.organization_id = customers.organization_id and om.user_id = (select auth.uid()) and om.active = true));
drop policy if exists customers_insert_org_member on public.customers;
create policy customers_insert_org_member on public.customers for insert to authenticated
with check (exists (select 1 from public.organization_members om where om.organization_id = customers.organization_id and om.user_id = (select auth.uid()) and om.active = true));
drop policy if exists customers_update_org_member on public.customers;
create policy customers_update_org_member on public.customers for update to authenticated
using (exists (select 1 from public.organization_members om where om.organization_id = customers.organization_id and om.user_id = (select auth.uid()) and om.active = true))
with check (exists (select 1 from public.organization_members om where om.organization_id = customers.organization_id and om.user_id = (select auth.uid()) and om.active = true));
drop policy if exists customers_delete_org_member on public.customers;
create policy customers_delete_org_member on public.customers for delete to authenticated
using (exists (select 1 from public.organization_members om where om.organization_id = customers.organization_id and om.user_id = (select auth.uid()) and om.active = true));

drop policy if exists customer_interactions_select_org_member on public.customer_interactions;
create policy customer_interactions_select_org_member on public.customer_interactions for select to authenticated
using (exists (select 1 from public.organization_members om where om.organization_id = customer_interactions.organization_id and om.user_id = (select auth.uid()) and om.active = true));
drop policy if exists customer_interactions_insert_org_member on public.customer_interactions;
create policy customer_interactions_insert_org_member on public.customer_interactions for insert to authenticated
with check (
    exists (select 1 from public.organization_members om where om.organization_id = customer_interactions.organization_id and om.user_id = (select auth.uid()) and om.active = true)
    and exists (select 1 from public.customers c where c.id = customer_interactions.customer_id and c.organization_id = customer_interactions.organization_id)
);
drop policy if exists customer_interactions_update_org_member on public.customer_interactions;
create policy customer_interactions_update_org_member on public.customer_interactions for update to authenticated
using (exists (select 1 from public.organization_members om where om.organization_id = customer_interactions.organization_id and om.user_id = (select auth.uid()) and om.active = true))
with check (exists (select 1 from public.organization_members om where om.organization_id = customer_interactions.organization_id and om.user_id = (select auth.uid()) and om.active = true));
drop policy if exists customer_interactions_delete_org_member on public.customer_interactions;
create policy customer_interactions_delete_org_member on public.customer_interactions for delete to authenticated
using (exists (select 1 from public.organization_members om where om.organization_id = customer_interactions.organization_id and om.user_id = (select auth.uid()) and om.active = true));

grant select, insert, update, delete on public.customers to authenticated;
grant select, insert, update, delete on public.customer_interactions to authenticated;
revoke all on public.customers from anon;
revoke all on public.customer_interactions from anon;
