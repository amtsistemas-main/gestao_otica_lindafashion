create or replace function public.finalize_sales_order(
 p_organization_id uuid,
 p_customer_id uuid,
 p_order_number text,
 p_subtotal numeric,
 p_discount numeric,
 p_total numeric,
 p_payment_method text,
 p_notes text,
 p_items jsonb
) returns jsonb
language plpgsql security invoker set search_path = public
as $$
declare
 v_order_id uuid;
 v_user_id uuid := auth.uid();
 v_item jsonb;
 v_product public.products%rowtype;
 v_qty numeric;
 v_price numeric;
 v_discount numeric;
 v_line_total numeric;
 v_order_number text := nullif(trim(p_order_number), '');
begin
 if v_user_id is null then raise exception 'Sessão autenticada obrigatória.'; end if;
 if not exists (select 1 from public.organization_members om where om.organization_id=p_organization_id and om.user_id=v_user_id and om.active=true) then raise exception 'Usuário sem vínculo ativo com esta organização.'; end if;
 if v_order_number is null then raise exception 'Número do pedido obrigatório.'; end if;
 if jsonb_typeof(p_items) <> 'array' or jsonb_array_length(p_items)=0 then raise exception 'A venda precisa conter itens.'; end if;
 if p_subtotal < 0 or p_discount < 0 or p_total < 0 or p_total <> p_subtotal-p_discount then raise exception 'Totais inconsistentes.'; end if;
 if p_customer_id is not null and not exists(select 1 from public.customers c where c.id=p_customer_id and c.organization_id=p_organization_id and c.active=true) then raise exception 'Cliente inválido ou inativo para esta organização.'; end if;
 insert into public.sales_orders(organization_id,customer_id,order_number,status,subtotal,discount,total,payment_method,notes,created_by)
 values(p_organization_id,p_customer_id,v_order_number,'completed',p_subtotal,p_discount,p_total,coalesce(p_payment_method,''),coalesce(p_notes,''),v_user_id) returning id into v_order_id;
 for v_item in select value from jsonb_array_elements(p_items) loop
  v_qty := (v_item->>'quantity')::numeric; v_price := (v_item->>'unit_price')::numeric; v_discount := coalesce((v_item->>'discount')::numeric,0); v_line_total := (v_item->>'line_total')::numeric;
  if v_qty <= 0 or v_qty <> trunc(v_qty) or v_price < 0 or v_discount < 0 or v_line_total < 0 or v_line_total <> v_qty*v_price-v_discount then raise exception 'Item da venda com quantidade ou valores inválidos.'; end if;
  select * into v_product from public.products where id=(v_item->>'product_id')::uuid and organization_id=p_organization_id and active=true for update;
  if not found then raise exception 'Produto não encontrado ou inativo.'; end if;
  if v_product.stock_quantity < v_qty then raise exception 'Estoque insuficiente para o produto: %.', v_product.name; end if;
  update public.products set stock_quantity=stock_quantity-v_qty, updated_at=now() where id=v_product.id and organization_id=p_organization_id;
  insert into public.sales_order_items(organization_id,sales_order_id,product_id,product_name,sku,quantity,unit_price,discount,line_total)
  values(p_organization_id,v_order_id,v_product.id,v_product.name,coalesce(v_product.sku,''),v_qty,v_price,v_discount,v_line_total);
 end loop;
 insert into public.financial_entries(organization_id,direction,category,description,amount,due_date,status,paid_at,payment_method,counterparty,reference,notes,created_by)
 values(p_organization_id,'entrada','Vendas','Venda '||v_order_number,p_total,current_date,'pago',current_date,coalesce(p_payment_method,''),coalesce((select c.full_name from public.customers c where c.id=p_customer_id and c.organization_id=p_organization_id),'Venda avulsa'),v_order_number,coalesce(p_notes,''),v_user_id);
 return jsonb_build_object('id',v_order_id,'order_number',v_order_number,'status','completed','total',p_total);
end;
$$;
revoke all on function public.finalize_sales_order(uuid,uuid,text,numeric,numeric,numeric,text,text,jsonb) from public, anon;
grant execute on function public.finalize_sales_order(uuid,uuid,text,numeric,numeric,numeric,text,text,jsonb) to authenticated;