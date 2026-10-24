-- Atomic receiving workflow for supplier purchase requests.
create or replace function public.receive_purchase_request_item(
    p_purchase_request_item_id uuid,
    p_quantity_to_receive integer,
    p_reference text default ''
) returns jsonb
language plpgsql
security invoker
set search_path = public
as $$
declare
    v_org uuid;
    v_item public.purchase_request_items%rowtype;
    v_request public.purchase_requests%rowtype;
    v_product public.products%rowtype;
    v_new_stock integer;
    v_total_items integer;
    v_complete_items integer;
    v_new_status text;
begin
    if p_quantity_to_receive is null or p_quantity_to_receive <= 0 then
        raise exception 'A quantidade recebida deve ser maior que zero.';
    end if;

    select organization_id into v_org
    from public.organization_members
    where user_id = (select auth.uid()) and active = true
    order by created_at limit 1;
    if v_org is null then raise exception 'Usuário sem organização ativa.'; end if;

    select * into v_item
    from public.purchase_request_items
    where id = p_purchase_request_item_id and organization_id = v_org
    for update;
    if not found then raise exception 'Item de compra não encontrado.'; end if;

    select * into v_request
    from public.purchase_requests
    where id = v_item.purchase_request_id and organization_id = v_org
    for update;
    if not found then raise exception 'Solicitação de compra não encontrada.'; end if;
    if v_request.status not in ('solicitada','aprovada','recebida_parcial') then
        raise exception 'Esta solicitação não aceita recebimento no status atual.';
    end if;
    if v_item.quantity_received + p_quantity_to_receive > v_item.quantity_requested then
        raise exception 'A quantidade recebida excede o saldo pendente do item.';
    end if;

    select * into v_product
    from public.products
    where id = v_item.product_id and organization_id = v_org and active = true
    for update;
    if not found then raise exception 'Produto não encontrado ou inativo.'; end if;

    v_new_stock := v_product.stock_quantity + p_quantity_to_receive;
    update public.products set stock_quantity = v_new_stock
    where id = v_product.id and organization_id = v_org;

    insert into public.stock_movements(
        organization_id, product_id, movement_type, quantity,
        previous_quantity, resulting_quantity, reason, reference, created_by
    ) values (
        v_org, v_product.id, 'entrada', p_quantity_to_receive,
        v_product.stock_quantity, v_new_stock, 'Recebimento de compra',
        coalesce(nullif(trim(p_reference),''), 'PC-' || v_request.request_number::text),
        (select auth.uid())
    );

    update public.purchase_request_items
    set quantity_received = quantity_received + p_quantity_to_receive
    where id = v_item.id;

    select count(*), count(*) filter (where quantity_received = quantity_requested)
    into v_total_items, v_complete_items
    from public.purchase_request_items
    where purchase_request_id = v_request.id and organization_id = v_org;

    if v_total_items > 0 and v_total_items = v_complete_items then
        v_new_status := 'recebida';
    else
        v_new_status := 'recebida_parcial';
    end if;
    update public.purchase_requests set status = v_new_status, updated_at = now()
    where id = v_request.id;

    return jsonb_build_object(
        'purchase_request_id', v_request.id,
        'product_id', v_product.id,
        'quantity_received_now', p_quantity_to_receive,
        'stock_before', v_product.stock_quantity,
        'stock_after', v_new_stock,
        'request_status', v_new_status
    );
end;
$$;

grant execute on function public.receive_purchase_request_item(uuid,integer,text) to authenticated;
comment on function public.receive_purchase_request_item(uuid,integer,text) is 'Recebe mercadoria atomicamente, atualiza saldo, histórico, quantidade recebida e status da solicitação.';
