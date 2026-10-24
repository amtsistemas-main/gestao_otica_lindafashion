alter table public.products add constraint products_id_organization_unique unique (id, organization_id);
create table if not exists public.sales_orders (
 id uuid primary key default gen_random_uuid(),
 organization_id uuid not null references public.organizations(id) on delete cascade,
 customer_id uuid,
 order_number text not null,
 status text not null default 'draft' check (status in ('draft','confirmed','completed','cancelled')),
 subtotal numeric(12,2) not null default 0 check (subtotal >= 0),
 discount numeric(12,2) not null default 0 check (discount >= 0),
 total numeric(12,2) not null default 0 check (total >= 0),
 payment_method text not null default '',
 notes text not null default '',
 created_by uuid references auth.users(id) on delete set null,
 created_at timestamptz not null default now(),
 updated_at timestamptz not null default now(),
 unique (organization_id, order_number),
 unique (id, organization_id),
 constraint sales_orders_customer_org_fk foreign key (customer_id, organization_id) references public.customers(id, organization_id) on delete restrict
);
create table if not exists public.sales_order_items (
 id uuid primary key default gen_random_uuid(),
 organization_id uuid not null references public.organizations(id) on delete cascade,
 sales_order_id uuid not null,
 product_id uuid,
 product_name text not null,
 sku text not null default '',
 quantity numeric(12,3) not null check (quantity > 0),
 unit_price numeric(12,2) not null check (unit_price >= 0),
 discount numeric(12,2) not null default 0 check (discount >= 0),
 line_total numeric(12,2) not null check (line_total >= 0),
 created_at timestamptz not null default now(),
 constraint sales_order_items_order_org_fk foreign key (sales_order_id, organization_id) references public.sales_orders(id, organization_id) on delete cascade,
 constraint sales_order_items_product_org_fk foreign key (product_id, organization_id) references public.products(id, organization_id) on delete restrict
);
create index if not exists sales_orders_org_created_idx on public.sales_orders (organization_id, created_at desc);
create index if not exists sales_orders_org_status_idx on public.sales_orders (organization_id, status);
create index if not exists sales_order_items_order_idx on public.sales_order_items (sales_order_id);
alter table public.sales_orders enable row level security;
alter table public.sales_order_items enable row level security;
drop policy if exists sales_orders_org_member_all on public.sales_orders;
create policy sales_orders_org_member_all on public.sales_orders for all to authenticated
using (exists (select 1 from public.organization_members om where om.organization_id = sales_orders.organization_id and om.user_id = (select auth.uid()) and om.active = true))
with check (exists (select 1 from public.organization_members om where om.organization_id = sales_orders.organization_id and om.user_id = (select auth.uid()) and om.active = true));
drop policy if exists sales_order_items_org_member_all on public.sales_order_items;
create policy sales_order_items_org_member_all on public.sales_order_items for all to authenticated
using (exists (select 1 from public.organization_members om where om.organization_id = sales_order_items.organization_id and om.user_id = (select auth.uid()) and om.active = true))
with check (exists (select 1 from public.organization_members om where om.organization_id = sales_order_items.organization_id and om.user_id = (select auth.uid()) and om.active = true));
grant select, insert, update, delete on public.sales_orders to authenticated;
grant select, insert, update, delete on public.sales_order_items to authenticated;
revoke all on public.sales_orders from anon;
revoke all on public.sales_order_items from anon;