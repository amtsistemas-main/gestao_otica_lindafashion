-- Finance module foundation: organization-scoped entries and payment-provider-ready references.
create table if not exists public.financial_entries (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null references public.organizations(id) on delete cascade,
    direction text not null check (direction in ('entrada', 'saida')),
    category text not null default 'Outros',
    description text not null check (length(trim(description)) > 0),
    amount numeric(14,2) not null check (amount > 0),
    due_date date not null default current_date,
    status text not null default 'pendente' check (status in ('pendente', 'pago', 'cancelado')),
    paid_at date,
    payment_method text not null default '',
    counterparty text not null default '',
    reference text not null default '',
    notes text not null default '',
    -- Future payment API integration fields: store provider identifiers/status only, never card data or secrets.
    payment_provider text not null default '',
    external_payment_id text not null default '',
    external_payment_status text not null default '',
    external_customer_id text not null default '',
    external_metadata jsonb not null default '{}'::jsonb check (jsonb_typeof(external_metadata) = 'object'),
    created_by uuid references auth.users(id) on delete set null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists financial_entries_org_due_idx
    on public.financial_entries(organization_id, due_date desc);
create index if not exists financial_entries_org_status_idx
    on public.financial_entries(organization_id, status, due_date);
create index if not exists financial_entries_org_direction_idx
    on public.financial_entries(organization_id, direction, due_date desc);
create index if not exists financial_entries_provider_payment_idx
    on public.financial_entries(payment_provider, external_payment_id)
    where external_payment_id <> '';

create or replace function public.set_financial_entries_updated_at()
returns trigger
language plpgsql
set search_path = public
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists financial_entries_updated_at on public.financial_entries;
create trigger financial_entries_updated_at
before update on public.financial_entries
for each row execute function public.set_financial_entries_updated_at();

alter table public.financial_entries enable row level security;

drop policy if exists "finance_select_organization_members" on public.financial_entries;
create policy "finance_select_organization_members"
on public.financial_entries for select to authenticated
using (exists (
    select 1 from public.organization_members m
    where m.organization_id = financial_entries.organization_id
      and m.user_id = (select auth.uid()) and m.active = true
));

drop policy if exists "finance_insert_organization_members" on public.financial_entries;
create policy "finance_insert_organization_members"
on public.financial_entries for insert to authenticated
with check (
    (created_by is null or created_by = (select auth.uid()))
    and exists (
        select 1 from public.organization_members m
        where m.organization_id = financial_entries.organization_id
          and m.user_id = (select auth.uid()) and m.active = true
    )
);

drop policy if exists "finance_update_organization_members" on public.financial_entries;
create policy "finance_update_organization_members"
on public.financial_entries for update to authenticated
using (exists (
    select 1 from public.organization_members m
    where m.organization_id = financial_entries.organization_id
      and m.user_id = (select auth.uid()) and m.active = true
))
with check (exists (
    select 1 from public.organization_members m
    where m.organization_id = financial_entries.organization_id
      and m.user_id = (select auth.uid()) and m.active = true
));

comment on table public.financial_entries is
'Organization-scoped cash entries, payables, receivables and sales. Payment API fields are identifiers/metadata only; never store card numbers, CVV, access tokens or provider secrets here.';
comment on column public.financial_entries.external_payment_id is 'External payment identifier for a future provider adapter; not a secret.';
comment on column public.financial_entries.external_metadata is 'Non-sensitive provider metadata only. Never store credentials or full payment card data.';
