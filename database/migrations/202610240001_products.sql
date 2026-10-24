-- Product catalog for Ótica Linda Fashion.
-- Apply in Supabase SQL Editor. Never expose the service_role key in the desktop app.

create extension if not exists pgcrypto;

create table if not exists public.organizations (
    id uuid primary key default gen_random_uuid(),
    name text not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.organization_members (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null references public.organizations(id) on delete cascade,
    user_id uuid not null references auth.users(id) on delete cascade,
    role text not null default 'member' check (role in ('owner', 'admin', 'member')),
    active boolean not null default true,
    created_at timestamptz not null default now(),
    unique (organization_id, user_id)
);

create index if not exists organization_members_user_active_idx
    on public.organization_members (user_id, active);

create table if not exists public.products (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null references public.organizations(id) on delete cascade,
    barcode text,
    sku text,
    name text not null,
    category text not null default '',
    brand text not null default '',
    cost_price numeric(12,2) not null default 0 check (cost_price >= 0),
    sale_price numeric(12,2) not null default 0 check (sale_price >= 0),
    discount_percent numeric(5,2) not null default 0 check (discount_percent between 0 and 100),
    stock_quantity integer not null default 0 check (stock_quantity >= 0),
    minimum_stock integer not null default 0 check (minimum_stock >= 0),
    description text not null default '',
    active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint products_name_nonempty check (length(trim(name)) > 0)
);

create unique index if not exists products_org_barcode_unique
    on public.products (organization_id, barcode)
    where barcode is not null and barcode <> '';
create unique index if not exists products_org_sku_unique
    on public.products (organization_id, sku)
    where sku is not null and sku <> '';
create index if not exists products_org_name_idx
    on public.products (organization_id, name);
create index if not exists products_org_active_idx
    on public.products (organization_id, active);

create or replace function public.set_products_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists products_set_updated_at on public.products;
create trigger products_set_updated_at
before update on public.products
for each row execute function public.set_products_updated_at();

alter table public.organizations enable row level security;
alter table public.organization_members enable row level security;
alter table public.products enable row level security;

drop policy if exists organizations_member_read on public.organizations;
create policy organizations_member_read on public.organizations
for select to authenticated
using (
    exists (
        select 1 from public.organization_members m
        where m.organization_id = organizations.id
          and m.user_id = (select auth.uid())
          and m.active = true
    )
);

drop policy if exists organization_members_self_read on public.organization_members;
create policy organization_members_self_read on public.organization_members
for select to authenticated
using (user_id = (select auth.uid()));

drop policy if exists products_member_read on public.products;
create policy products_member_read on public.products
for select to authenticated
using (
    exists (
        select 1 from public.organization_members m
        where m.organization_id = products.organization_id
          and m.user_id = (select auth.uid())
          and m.active = true
    )
);

drop policy if exists products_member_insert on public.products;
create policy products_member_insert on public.products
for insert to authenticated
with check (
    exists (
        select 1 from public.organization_members m
        where m.organization_id = products.organization_id
          and m.user_id = (select auth.uid())
          and m.active = true
          and m.role in ('owner', 'admin', 'member')
    )
);

drop policy if exists products_member_update on public.products;
create policy products_member_update on public.products
for update to authenticated
using (
    exists (
        select 1 from public.organization_members m
        where m.organization_id = products.organization_id
          and m.user_id = (select auth.uid())
          and m.active = true
    )
)
with check (
    exists (
        select 1 from public.organization_members m
        where m.organization_id = products.organization_id
          and m.user_id = (select auth.uid())
          and m.active = true
    )
);

comment on table public.products is 'Catalogo de produtos da ótica, isolado por organização.';
comment on column public.products.barcode is 'Código de barras lido por leitor USB ou informado manualmente.';
comment on column public.products.discount_percent is 'Percentual de desconto padrão aplicado ao preço de venda.';
