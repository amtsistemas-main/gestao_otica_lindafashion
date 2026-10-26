-- Fase 5 — Inteligência comercial e rentabilidade.
-- Os novos itens já gravam o custo no momento da venda (fase 4). Para o histórico anterior,
-- usa-se o custo atual do produto como melhor aproximação disponível, apenas onde não há custo.

update public.sales_order_items i
set unit_cost = p.cost_price,
    product_type = p.product_type
from public.products p
where p.id = i.product_id
  and p.organization_id = i.organization_id
  and i.unit_cost = 0;

create index if not exists sales_order_items_org_product_created_idx
    on public.sales_order_items (organization_id, product_id, created_at desc);
create index if not exists financial_entries_org_status_direction_idx
    on public.financial_entries (organization_id, direction, status, due_date);

comment on column public.sales_order_items.unit_cost is
'Custo unitário congelado na venda. Itens anteriores à fase 5 receberam o custo vigente do produto como aproximação.';
