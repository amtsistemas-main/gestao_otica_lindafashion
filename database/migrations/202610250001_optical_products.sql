-- Fase 1 — Gestão especializada de produtos ópticos.
-- Tipo de produto, características de armação/lente, reposição e itens sem controle de estoque.

alter table public.products
    add column if not exists product_type text not null default 'outro',
    add column if not exists model text not null default '',
    add column if not exists color text not null default '',
    add column if not exists size text not null default '',
    add column if not exists material text not null default '',
    add column if not exists gender text not null default '',
    add column if not exists lens_type text not null default '',
    add column if not exists lens_index text not null default '',
    add column if not exists lens_treatment text not null default '',
    add column if not exists contact_replacement text not null default '',
    add column if not exists reorder_quantity integer not null default 0,
    add column if not exists tracks_stock boolean not null default true;

alter table public.products drop constraint if exists products_product_type_check;
alter table public.products add constraint products_product_type_check
    check (product_type in ('armacao','lente_oftalmica','lente_contato','oculos_sol','acessorio','servico','outro'));

alter table public.products drop constraint if exists products_gender_check;
alter table public.products add constraint products_gender_check
    check (gender in ('','feminino','masculino','unissex','infantil'));

alter table public.products drop constraint if exists products_lens_type_check;
alter table public.products add constraint products_lens_type_check
    check (lens_type in ('','monofocal','bifocal','multifocal','ocupacional'));

alter table public.products drop constraint if exists products_reorder_quantity_check;
alter table public.products add constraint products_reorder_quantity_check
    check (reorder_quantity >= 0);

create index if not exists products_org_type_idx
    on public.products (organization_id, product_type, active);

comment on column public.products.product_type is 'armacao, lente_oftalmica, lente_contato, oculos_sol, acessorio, servico ou outro.';
comment on column public.products.minimum_stock is 'Ponto de reposição: ao atingir este saldo o produto entra no alerta de compra.';
comment on column public.products.reorder_quantity is 'Quantidade sugerida para a solicitação de compra (0 = calcular automaticamente).';
comment on column public.products.tracks_stock is 'Falso para serviços (montagem, ajuste) que não movimentam estoque.';
