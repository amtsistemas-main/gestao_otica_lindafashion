-- Complete supplier records and tenant-safe product/supplier relationship.
alter table public.suppliers
    add column if not exists legal_name text not null default '',
    add column if not exists trade_name text not null default '',
    add column if not exists document text not null default '',
    add column if not exists state_registration text not null default '',
    add column if not exists municipal_registration text not null default '',
    add column if not exists whatsapp text not null default '',
    add column if not exists website text not null default '',
    add column if not exists postal_code text not null default '',
    add column if not exists street text not null default '',
    add column if not exists address_number text not null default '',
    add column if not exists address_complement text not null default '',
    add column if not exists neighborhood text not null default '',
    add column if not exists city text not null default '',
    add column if not exists state text not null default '',
    add column if not exists payment_terms text not null default '',
    add column if not exists pix_key text not null default '',
    add column if not exists bank_name text not null default '',
    add column if not exists bank_branch text not null default '',
    add column if not exists bank_account text not null default '';

create unique index if not exists suppliers_id_org_unique on public.suppliers(id, organization_id);
create index if not exists suppliers_document_org_idx on public.suppliers(organization_id, document);
create index if not exists suppliers_active_name_idx on public.suppliers(organization_id, active, name);

alter table public.products add column if not exists supplier_id uuid;

do $$
begin
    if not exists (
        select 1 from pg_constraint
        where conname = 'products_supplier_org_fk'
          and conrelid = 'public.products'::regclass
    ) then
        alter table public.products
            add constraint products_supplier_org_fk
            foreign key (supplier_id, organization_id)
            references public.suppliers(id, organization_id)
            on delete set null (supplier_id);
    end if;
end $$;

create index if not exists products_supplier_org_idx
    on public.products(organization_id, supplier_id)
    where supplier_id is not null;

comment on column public.products.supplier_id is 'Fornecedor principal do produto, pertencente à mesma organização.';
comment on table public.suppliers is 'Cadastro completo de fornecedores da organização, incluindo dados fiscais, comerciais, endereço e pagamento.';
