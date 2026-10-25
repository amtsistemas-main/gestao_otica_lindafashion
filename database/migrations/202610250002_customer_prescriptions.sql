-- Fase 2 — Receitas oftálmicas estruturadas, histórico por cliente e vínculo com a venda.
-- As regras ópticas também são validadas no banco para impedir dados inconsistentes.

create table if not exists public.customer_prescriptions (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null references public.organizations(id) on delete cascade,
    customer_id uuid not null,
    prescribed_at date not null default current_date,
    expires_at date,
    source text not null default 'receita_externa'
        check (source in ('receita_externa','exame_interno','lensometria')),
    prescriber_name text not null default '',
    prescriber_registry text not null default '',
    -- Olho direito (OD)
    od_sphere numeric(5,2),
    od_cylinder numeric(5,2),
    od_axis smallint,
    od_addition numeric(4,2),
    od_dnp numeric(4,1),
    od_near_dnp numeric(4,1),
    od_height numeric(4,1),
    od_prism numeric(4,2),
    od_prism_base text not null default '',
    -- Olho esquerdo (OE)
    oe_sphere numeric(5,2),
    oe_cylinder numeric(5,2),
    oe_axis smallint,
    oe_addition numeric(4,2),
    oe_dnp numeric(4,1),
    oe_near_dnp numeric(4,1),
    oe_height numeric(4,1),
    oe_prism numeric(4,2),
    oe_prism_base text not null default '',
    lens_recommendation text not null default '',
    notes text not null default '',
    active boolean not null default true,
    created_by uuid references auth.users(id) on delete set null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (id, organization_id),
    constraint customer_prescriptions_customer_org_fk
        foreign key (customer_id, organization_id)
        references public.customers (id, organization_id) on delete cascade,
    constraint customer_prescriptions_dates_check
        check (expires_at is null or expires_at >= prescribed_at),
    -- Esférico e cilíndrico em passos de 0,25 D dentro de faixas clínicas
    constraint customer_prescriptions_sphere_check check (
        (od_sphere is null or (od_sphere between -30 and 30 and mod(od_sphere * 100, 25) = 0))
        and (oe_sphere is null or (oe_sphere between -30 and 30 and mod(oe_sphere * 100, 25) = 0))
    ),
    constraint customer_prescriptions_cylinder_check check (
        (od_cylinder is null or (od_cylinder between -15 and 15 and mod(od_cylinder * 100, 25) = 0))
        and (oe_cylinder is null or (oe_cylinder between -15 and 15 and mod(oe_cylinder * 100, 25) = 0))
    ),
    -- Eixo obrigatório quando há cilindro
    constraint customer_prescriptions_axis_check check (
        (od_axis is null or od_axis between 0 and 180)
        and (oe_axis is null or oe_axis between 0 and 180)
        and (coalesce(od_cylinder, 0) = 0 or od_axis is not null)
        and (coalesce(oe_cylinder, 0) = 0 or oe_axis is not null)
    ),
    constraint customer_prescriptions_addition_check check (
        (od_addition is null or (od_addition between 0.25 and 4.5 and mod(od_addition * 100, 25) = 0))
        and (oe_addition is null or (oe_addition between 0.25 and 4.5 and mod(oe_addition * 100, 25) = 0))
    ),
    constraint customer_prescriptions_dnp_check check (
        (od_dnp is null or od_dnp between 20 and 45)
        and (oe_dnp is null or oe_dnp between 20 and 45)
        and (od_near_dnp is null or od_near_dnp between 18 and 45)
        and (oe_near_dnp is null or oe_near_dnp between 18 and 45)
    ),
    constraint customer_prescriptions_height_check check (
        (od_height is null or od_height between 8 and 45)
        and (oe_height is null or oe_height between 8 and 45)
    ),
    constraint customer_prescriptions_prism_check check (
        (od_prism is null or od_prism between 0 and 15)
        and (oe_prism is null or oe_prism between 0 and 15)
    )
);

create index if not exists customer_prescriptions_customer_idx
    on public.customer_prescriptions (organization_id, customer_id, prescribed_at desc);
create index if not exists customer_prescriptions_expiry_idx
    on public.customer_prescriptions (organization_id, expires_at)
    where active = true and expires_at is not null;

create or replace function public.set_customer_prescriptions_updated_at()
returns trigger
language plpgsql
set search_path = public, pg_temp
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists customer_prescriptions_updated_at on public.customer_prescriptions;
create trigger customer_prescriptions_updated_at
before update on public.customer_prescriptions
for each row execute function public.set_customer_prescriptions_updated_at();

alter table public.customer_prescriptions enable row level security;

drop policy if exists customer_prescriptions_select_org_member on public.customer_prescriptions;
create policy customer_prescriptions_select_org_member on public.customer_prescriptions for select to authenticated
using (exists (select 1 from public.organization_members om where om.organization_id = customer_prescriptions.organization_id and om.user_id = (select auth.uid()) and om.active = true));

drop policy if exists customer_prescriptions_insert_org_member on public.customer_prescriptions;
create policy customer_prescriptions_insert_org_member on public.customer_prescriptions for insert to authenticated
with check (
    exists (select 1 from public.organization_members om where om.organization_id = customer_prescriptions.organization_id and om.user_id = (select auth.uid()) and om.active = true)
    and exists (select 1 from public.customers c where c.id = customer_prescriptions.customer_id and c.organization_id = customer_prescriptions.organization_id)
);

drop policy if exists customer_prescriptions_update_org_member on public.customer_prescriptions;
create policy customer_prescriptions_update_org_member on public.customer_prescriptions for update to authenticated
using (exists (select 1 from public.organization_members om where om.organization_id = customer_prescriptions.organization_id and om.user_id = (select auth.uid()) and om.active = true))
with check (exists (select 1 from public.organization_members om where om.organization_id = customer_prescriptions.organization_id and om.user_id = (select auth.uid()) and om.active = true));

grant select, insert, update on public.customer_prescriptions to authenticated;
revoke all on public.customer_prescriptions from anon;

-- Vínculo da venda com a receita utilizada e as medidas da armação escolhida.
alter table public.sales_orders
    add column if not exists prescription_id uuid,
    add column if not exists frame_measurements jsonb not null default '{}'::jsonb;

do $$
begin
    if not exists (select 1 from pg_constraint where conname = 'sales_orders_prescription_org_fk') then
        alter table public.sales_orders
            add constraint sales_orders_prescription_org_fk
            foreign key (prescription_id, organization_id)
            references public.customer_prescriptions (id, organization_id)
            on delete set null (prescription_id);
    end if;
end $$;

comment on table public.customer_prescriptions is 'Receitas oftálmicas estruturadas por cliente (OD/OE), com histórico e validade.';
