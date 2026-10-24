-- Atomic purchase receiving and zero-stock adjustment support.
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
    if p_quantity < 0 or (p_quantity = 0 and p_movement_type <> 'ajuste') then
        raise exception 'A quantidade deve ser maior que zero; ajuste pode definir saldo zero.';
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
    if p_movement_type = 'ajuste' and v_result = v_previous then
        raise exception 'O saldo informado já corresponde ao estoque atual.';
    end if;

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

create or replace function public.receive_purchase_request_item(
    p_purchase_request_item_id uuid,
    p_quantity integer,
    p_reference text default '',
    p_reason text default 'Recebimento de compra'
) returns jsonb
language plpgsql
security invoker
set search_path = public
as $$
declare
    v_item public.purchase_request_items%rowtype;
    v_request public.purchase_requests%rowtype;
    v_product public.products%rowtype;
    v_org uuid;
    v_new_stock integer;
    v_new_received integer;
    v_status text;
begin
    if p_quantity <= 0 then
        raise exception 'A quantidade recebida deve ser maior que zero.';
    end if;

    select * into v_item
    from public.purchase_request_items
    where id = p_purchase_request_item_id
    for update;
    if not found then raise exception 'Item de compra não encontrado.'; end if;

    select * into v_request
    from public.purchase_requests
    where id = v_item.purchase_request_id
    for update;
    if not found then raise exception 'Solicitação de compra não encontrada.'; end if;

    v_org := v_request.organization_id;
    if not exists (
        select 1 from public.organization_members m
        where m.organization_id = v_org
          and m.user_id = (select auth.uid())
          and m.active = true
    ) then
        raise exception 'Sem permissão para receber compras desta organização.';
    end if;
    if v_request.status not in ('solicitada','aprovada','recebida_parcial') then
        raise exception 'Esta solicitação não permite recebimento no status atual.';
    end if;
    if v_item.organization_id <> v_org then
        raise exception 'O item não pertence à organização da solicitação.';
    end if;
    if v_item.quantity_received + p_quantity > v_item.quantity_requested then
        raise exception 'A quantidade recebida ultrapassa o saldo pendente do item.';
    end if;

    select * into v_product
    from public.products
    where id = v_item.product_id
      and organization_id = v_org
      and active = true
    for update;
    if not found then raise exception 'Produto não encontrado ou inativo.'; end if;

    v_new_stock := v_product.stock_quantity + p_quantity;
    v_new_received := v_item.quantity_received + p_quantity;

    update public.products
    set stock_quantity = v_new_stock
    where id = v_product.id and organization_id = v_org;

    insert into public.stock_movements(
        organization_id, product_id, movement_type, quantity,
        previous_quantity, resulting_quantity, reason, reference, created_by
    ) values (
        v_org, v_product.id, 'entrada', p_quantity,
        v_product.stock_quantity, v_new_stock, coalesce(p_reason, 'Recebimento de compra'),
        coalesce(p_reference, ''), (select auth.uid())
    );

    update public.purchase_request_items
    set quantity_received = v_new_received
    where id = v_item.id and organization_id = v_org;

    if not exists (
        select 1 from public.purchase_request_items i
        where i.purchase_request_id = v_request.id
          and i.quantity_received < i.quantity_requested
    ) then
        v_status := 'recebida';
    else
        v_status := 'recebida_parcial';
    end if;

    update public.purchase_requests
    set status = v_status, updated_at = now()
    where id = v_request.id and organization_id = v_org;

    return jsonb_build_object(
        'purchase_request_id', v_request.id,
        'product_id', v_product.id,
        'quantity_received_now', p_quantity,
        'item_quantity_received', v_new_received,
        'item_quantity_pending', v_item.quantity_requested - v_new_received,
        'stock_quantity', v_new_stock,
        'request_status', v_status
    );
end;
$$;

grant execute on function public.receive_purchase_request_item(uuid,integer,text,text) to authenticated;
