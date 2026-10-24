-- Order status tracking for customer follow-up and future notifications.
create table if not exists public.customer_orders (
 id uuid primary key default gen_random_uuid(),
 organization_id uuid not null references public.organizations(id) on delete cascade,
 customer_id uuid not null,
 order_number text not null default '',
 description text not null default '',
 status text not null default 'em_desenvolvimento' check (status in ('em_desenvolvimento','pronto','entregue','cancelado')),
 expected_at date,
 completed_at timestamptz,
 delivered_at timestamptz,
 notes text not null default '',
 created_by uuid references auth.users(id) on delete set null,
 created_at timestamptz not null default now(),
 updated_at timestamptz not null default now(),
 constraint customer_orders_customer_org_fk foreign key (customer_id, organization_id) references public.customers(id, organization_id) on delete cascade,
 unique (organization_id, order_number)
);
create index if not exists customer_orders_org_customer_idx on public.customer_orders (organization_id, customer_id, created_at desc);
create index if not exists customer_orders_org_status_idx on public.customer_orders (organization_id, status, expected_at);
alter table public.customer_orders enable row level security;
drop policy if exists customer_orders_select_org_member on public.customer_orders;
create policy customer_orders_select_org_member on public.customer_orders for select to authenticated using (exists (select 1 from public.organization_members om where om.organization_id=customer_orders.organization_id and om.user_id=(select auth.uid()) and om.active=true));
drop policy if exists customer_orders_insert_org_member on public.customer_orders;
create policy customer_orders_insert_org_member on public.customer_orders for insert to authenticated with check (exists (select 1 from public.organization_members om where om.organization_id=customer_orders.organization_id and om.user_id=(select auth.uid()) and om.active=true) and exists (select 1 from public.customers c where c.id=customer_orders.customer_id and c.organization_id=customer_orders.organization_id));
drop policy if exists customer_orders_update_org_member on public.customer_orders;
create policy customer_orders_update_org_member on public.customer_orders for update to authenticated using (exists (select 1 from public.organization_members om where om.organization_id=customer_orders.organization_id and om.user_id=(select auth.uid()) and om.active=true)) with check (exists (select 1 from public.organization_members om where om.organization_id=customer_orders.organization_id and om.user_id=(select auth.uid()) and om.active=true));
drop policy if exists customer_orders_delete_org_member on public.customer_orders;
create policy customer_orders_delete_org_member on public.customer_orders for delete to authenticated using (exists (select 1 from public.organization_members om where om.organization_id=customer_orders.organization_id and om.user_id=(select auth.uid()) and om.active=true));
grant select, insert, update, delete on public.customer_orders to authenticated;
revoke all on public.customer_orders from anon;
