-- Inventory, suppliers and purchase requests for Ótica Linda Fashion.
create table if not exists public.suppliers (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null references public.organizations(id) on delete cascade,
    name text not null check (length(trim(name)) > 0),
    contact_name text not null default '',
    phone text not null default '',
    email text not null default '',
    notes text not null default '',
    active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create index if not exists suppliers_org_name_idx on public.suppliers(organization_id, name);

create table if not exists public.stock_movements (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null references public.organizations(id) on delete cascade,
    product_id uuid not null references public.products(id) on delete restrict,
    movement_type text not null check (movement_type in ('entrada','saida','ajuste')),
    quantity integer not null check (quantity > 0),
    previous_quantity integer not null check (previous_quantity >= 0),
    resulting_quantity integer not null check (resulting_quantity >= 0),
    reason text not null default '',
    reference text not null default '',
    created_by uuid references auth.users(id) on delete set null,
    created_at timestamptz not null default now()
);
create index if not exists stock_movements_org_date_idx on public.stock_movements(organization_id, created_at desc);
create index if not exists stock_movements_product_idx on public.stock_movements(product_id, created_at desc);

create table if not exists public.purchase_requests (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null references public.organizations(id) on delete cascade,
    supplier_id uuid references public.suppliers(id) on delete set null,
    request_number bigint generated always as identity,
    status text not null default 'rascunho' check (status in ('rascunho','solicitada','aprovada','recebida_parcial','recebida','cancelada')),
    notes text not null default '',
    created_by uuid references auth.users(id) on delete set null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create index if not exists purchase_requests_org_status_idx on public.purchase_requests(organization_id, status, created_at desc);

create table if not exists public.purchase_request_items (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null references public.organizations(id) on delete cascade,
    purchase_request_id uuid not null references public.purchase_requests(id) on delete cascade,
    product_id uuid not null references public.products(id) on delete restrict,
    quantity_requested integer not null check (quantity_requested > 0),
    quantity_received integer not null default 0 check (quantity_received >= 0 and quantity_received <= quantity_requested),
    unit_cost numeric(12,2) not null default 0 check (unit_cost >= 0),
    created_at timestamptz not null default now(),
    unique (purchase_request_id, product_id)
);

create or replace function public.record_stock_movement(
    p_product_id uuid,
    p_movement_type text,
    p_quantity integer,
    p_reason text default '',
    p_reference text default ''
) returns public.stock_movements
language plpgsql
security invoker
set search_path = public
as $$
declare
    v_product public.products%rowtype;
    v_previous integer;
    v_result integer;
    v_movement public.stock_movements%rowtype;
    v_org uuid;
begin
    if p_movement_type not in ('entrada','saida','ajuste') then
        raise exception 'Tipo de movimentação inválido.';
    end if;
    if p_quantity <= 0 then
        raise exception 'A quantidade deve ser maior que zero.';
    end if;
    select organization_id into v_org
    from public.organization_members
    where user_id = (select auth.uid()) and active = true
    order by created_at limit 1;
    if v_org is null then raise exception 'Usuário sem organização ativa.'; end if;

    select * into v_product from public.products
    where id = p_product_id and organization_id = v_org and active = true
    for update;
    if not found then raise exception 'Produto não encontrado ou inativo.'; end if;

    v_previous := v_product.stock_quantity;
    if p_movement_type = 'entrada' then
        v_result := v_previous + p_quantity;
    elsif p_movement_type = 'saida' then
        v_result := v_previous - p_quantity;
    else
        v_result := p_quantity;
    end if;
    if v_result < 0 then raise exception 'Estoque insuficiente para esta saída.'; end if;

    update public.products set stock_quantity = v_result
    where id = p_product_id and organization_id = v_org;

    insert into public.stock_movements(
        organization_id, product_id, movement_type, quantity,
        previous_quantity, resulting_quantity, reason, reference, created_by
    ) values (
        v_org, p_product_id, p_movement_type,
        case when p_movement_type = 'ajuste' then abs(v_result-v_previous) else p_quantity end,
        v_previous, v_result, coalesce(p_reason,''), coalesce(p_reference,''), (select auth.uid())
    ) returning * into v_movement;
    return v_movement;
end;
$$;

alter table public.suppliers enable row level security;
alter table public.stock_movements enable row level security;
alter table public.purchase_requests enable row level security;
alter table public.purchase_request_items enable row level security;

drop policy if exists suppliers_member_all on public.suppliers;
create policy suppliers_member_all on public.suppliers for all to authenticated
using (exists (select 1 from public.organization_members m where m.organization_id=suppliers.organization_id and m.user_id=(select auth.uid()) and m.active=true))
with check (exists (select 1 from public.organization_members m where m.organization_id=suppliers.organization_id and m.user_id=(select auth.uid()) and m.active=true));

drop policy if exists stock_movements_member_read on public.stock_movements;
create policy stock_movements_member_read on public.stock_movements for select to authenticated
using (exists (select 1 from public.organization_members m where m.organization_id=stock_movements.organization_id and m.user_id=(select auth.uid()) and m.active=true));

drop policy if exists stock_movements_member_insert on public.stock_movements;
create policy stock_movements_member_insert on public.stock_movements for insert to authenticated
with check (exists (select 1 from public.organization_members m where m.organization_id=stock_movements.organization_id and m.user_id=(select auth.uid()) and m.active=true));

drop policy if exists purchase_requests_member_all on public.purchase_requests;
create policy purchase_requests_member_all on public.purchase_requests for all to authenticated
using (exists (select 1 from public.organization_members m where m.organization_id=purchase_requests.organization_id and m.user_id=(select auth.uid()) and m.active=true))
with check (exists (select 1 from public.organization_members m where m.organization_id=purchase_requests.organization_id and m.user_id=(select auth.uid()) and m.active=true));

drop policy if exists purchase_request_items_member_all on public.purchase_request_items;
create policy purchase_request_items_member_all on public.purchase_request_items for all to authenticated
using (exists (select 1 from public.organization_members m where m.organization_id=purchase_request_items.organization_id and m.user_id=(select auth.uid()) and m.active=true))
with check (exists (select 1 from public.organization_members m where m.organization_id=purchase_request_items.organization_id and m.user_id=(select auth.uid()) and m.active=true));

grant select, insert, update on public.suppliers to authenticated;
grant select, insert on public.stock_movements to authenticated;
grant select, insert, update on public.purchase_requests to authenticated;
grant select, insert, update, delete on public.purchase_request_items to authenticated;
grant execute on function public.record_stock_movement(uuid,text,integer,text,text) to authenticated;

comment on table public.stock_movements is 'Histórico auditável de alterações no estoque; saldo atualizado atomicamente.';
comment on table public.purchase_requests is 'Solicitações de compra vinculadas a fornecedor e organização.';
