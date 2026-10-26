-- Fase 4 (integridade) — vendas gravadas somente pelas funções transacionais.
-- Sem isto, um membro poderia inserir/alterar vendas direto na API e contornar o limite de
-- desconto, a conferência dos pagamentos, a baixa de estoque e o estorno.
-- As funções passam a security definer; elas mesmas validam sessão, vínculo e papel.

alter function public.finalize_sales_order_v2(uuid,uuid,jsonb,jsonb,text,text,uuid,jsonb,uuid,boolean,uuid,boolean,date,text)
    security definer;
alter function public.cancel_sales_order(uuid, text) security definer;

-- A função antiga não conhece pagamentos múltiplos, limite de desconto nem serviços sem estoque.
revoke all on function public.finalize_sales_order(uuid,uuid,text,numeric,numeric,numeric,text,text,jsonb) from public, anon, authenticated;

-- Vendas, itens e pagamentos: leitura para a equipe; escrita apenas via RPC.
drop policy if exists sales_orders_org_member_all on public.sales_orders;
drop policy if exists sales_orders_member_read on public.sales_orders;
create policy sales_orders_member_read on public.sales_orders for select to authenticated
using (public.is_org_member(organization_id));

drop policy if exists sales_order_items_org_member_all on public.sales_order_items;
drop policy if exists sales_order_items_member_read on public.sales_order_items;
create policy sales_order_items_member_read on public.sales_order_items for select to authenticated
using (public.is_org_member(organization_id));

drop policy if exists sales_order_payments_member_insert on public.sales_order_payments;

revoke insert, update, delete on public.sales_orders, public.sales_order_items, public.sales_order_payments from authenticated, anon;
revoke all on public.sales_orders, public.sales_order_items from anon;
grant select on public.sales_orders, public.sales_order_items, public.sales_order_payments to authenticated;
