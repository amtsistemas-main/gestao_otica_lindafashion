-- Vendedor em cada venda, para o repasse de comissões.
--
-- finalize_sales_order_v2 ganha p_seller_id (opcional, último parâmetro). O vendedor precisa
-- ser um usuário ativo da organização (cadastrado pelo administrador); sem escolha, fica quem
-- registra a venda, como antes. Na conversão de orçamento, o vendedor escolhido prevalece.

drop function if exists public.finalize_sales_order_v2(uuid, uuid, jsonb, jsonb, text, text, uuid, jsonb, uuid, boolean, uuid, boolean, date, text, text);

CREATE OR REPLACE FUNCTION public.finalize_sales_order_v2(p_organization_id uuid, p_customer_id uuid, p_items jsonb, p_payments jsonb DEFAULT '[]'::jsonb, p_notes text DEFAULT ''::text, p_discount_reason text DEFAULT ''::text, p_prescription_id uuid DEFAULT NULL::uuid, p_frame_measurements jsonb DEFAULT '{}'::jsonb, p_idempotency_key uuid DEFAULT NULL::uuid, p_as_quote boolean DEFAULT false, p_quote_id uuid DEFAULT NULL::uuid, p_create_lab_order boolean DEFAULT false, p_lab_expected_at date DEFAULT NULL::date, p_lens_description text DEFAULT ''::text, p_order_status text DEFAULT 'aguardando_envio'::text, p_seller_id uuid DEFAULT NULL::uuid)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', 'pg_temp'
AS $function$
declare
    v_user uuid := auth.uid();
    v_seller uuid;
    v_role text;
    v_max_discount numeric;
    v_existing public.sales_orders%rowtype;
    v_order_id uuid;
    v_order_number text;
    v_item jsonb;
    v_payment jsonb;
    v_product public.products%rowtype;
    v_qty numeric;
    v_price numeric;
    v_discount numeric;
    v_subtotal numeric := 0;
    v_discount_total numeric := 0;
    v_total numeric := 0;
    v_paid_total numeric := 0;
    v_discount_pct numeric := 0;
    v_authorized_by uuid;
    v_customer_name text := 'Venda avulsa';
    v_method text;
    v_method_label text;
    v_amount numeric;
    v_installments integer;
    v_receivable boolean;
    v_first_due date;
    v_part numeric;
    v_i integer;
    v_payment_summary text := '';
    v_lab_order_id uuid;
    v_now_local timestamp := now() at time zone 'America/Sao_Paulo';
begin
    if v_user is null then raise exception 'Sessão autenticada obrigatória.'; end if;
    select role into v_role from public.organization_members
    where organization_id = p_organization_id and user_id = v_user and active = true;
    if v_role is null then raise exception 'Usuário sem vínculo ativo com esta organização.'; end if;
    -- Vendedor da venda (comissões): usuário ativo da loja; sem escolha, quem registra.
    v_seller := coalesce(p_seller_id, v_user);
    if not exists (select 1 from public.organization_members m
                   where m.organization_id = p_organization_id and m.user_id = v_seller and m.active = true) then
        raise exception 'Vendedor inválido: escolha um usuário ativo da loja.';
    end if;
    if jsonb_typeof(p_items) <> 'array' or jsonb_array_length(p_items) = 0 then
        raise exception 'A venda precisa conter itens.';
    end if;

    -- Idempotência: uma nova tentativa com a mesma chave devolve a venda já registrada.
    if p_idempotency_key is not null then
        select * into v_existing from public.sales_orders
        where organization_id = p_organization_id and idempotency_key = p_idempotency_key;
        if found then
            return jsonb_build_object('id', v_existing.id, 'order_number', v_existing.order_number,
                'status', v_existing.status, 'total', v_existing.total, 'duplicate', true);
        end if;
    end if;

    if p_customer_id is not null then
        select full_name into v_customer_name from public.customers
        where id = p_customer_id and organization_id = p_organization_id and active = true;
        if not found then raise exception 'Cliente inválido ou inativo para esta organização.'; end if;
    end if;
    if p_prescription_id is not null and not exists (
        select 1 from public.customer_prescriptions
        where id = p_prescription_id and organization_id = p_organization_id and customer_id = p_customer_id
    ) then
        raise exception 'A receita selecionada não pertence a este cliente.';
    end if;

    -- Totais sempre recalculados no servidor.
    for v_item in select value from jsonb_array_elements(p_items) loop
        v_qty := (v_item->>'quantity')::numeric;
        v_price := (v_item->>'unit_price')::numeric;
        v_discount := coalesce((v_item->>'discount')::numeric, 0);
        if v_qty is null or v_qty <= 0 or v_qty <> trunc(v_qty) or v_price is null or v_price < 0
           or v_discount < 0 or v_discount > v_qty * v_price then
            raise exception 'Item da venda com quantidade ou valores inválidos.';
        end if;
        v_subtotal := v_subtotal + v_qty * v_price;
        v_discount_total := v_discount_total + v_discount;
    end loop;
    v_subtotal := round(v_subtotal, 2);
    v_discount_total := round(v_discount_total, 2);
    v_total := v_subtotal - v_discount_total;
    if v_subtotal > 0 then
        v_discount_pct := round(v_discount_total / v_subtotal * 100, 2);
    end if;

    -- Limite único de desconto da loja; administradores e donos podem exceder.
    select max_discount_percent into v_max_discount from public.organization_settings
    where organization_id = p_organization_id;
    v_max_discount := coalesce(v_max_discount, 10);
    if v_discount_pct > v_max_discount then
        if v_role not in ('owner', 'admin') then
            raise exception 'Desconto de % %% excede o limite da loja de % %%. Solicite a venda a um administrador.',
                v_discount_pct, v_max_discount;
        end if;
        if coalesce(trim(p_discount_reason), '') = '' then
            raise exception 'Informe o motivo do desconto acima do limite da loja.';
        end if;
        v_authorized_by := v_user;
    end if;

    -- Pagamentos (somente para venda).
    if not p_as_quote then
        if jsonb_typeof(p_payments) <> 'array' or (jsonb_array_length(p_payments) = 0 and v_total > 0) then
            raise exception 'Informe as formas de pagamento da venda.';
        end if;
        for v_payment in select value from jsonb_array_elements(p_payments) loop
            v_method := v_payment->>'method';
            v_amount := round((v_payment->>'amount')::numeric, 2);
            v_installments := coalesce((v_payment->>'installments')::integer, 1);
            if v_method not in ('dinheiro','pix','debito','credito','transferencia','crediario','boleto','outro')
               or v_amount is null or v_amount <= 0 or v_installments not between 1 and 24 then
                raise exception 'Pagamento com forma, valor ou parcelas inválidos.';
            end if;
            v_paid_total := v_paid_total + v_amount;
        end loop;
        if round(v_paid_total, 2) <> v_total then
            raise exception 'A soma dos pagamentos (%) difere do total da venda (%).', v_paid_total, v_total;
        end if;
    end if;

    -- Cabeçalho: novo registro ou conversão/atualização de orçamento existente.
    if p_quote_id is not null then
        select * into v_existing from public.sales_orders
        where id = p_quote_id and organization_id = p_organization_id for update;
        if not found or v_existing.status <> 'draft' then
            raise exception 'Orçamento não encontrado ou já convertido.';
        end if;
        v_order_id := v_existing.id;
        v_order_number := v_existing.order_number;
        delete from public.sales_order_items where sales_order_id = v_order_id and organization_id = p_organization_id;
        update public.sales_orders set
            customer_id = p_customer_id,
            status = case when p_as_quote then 'draft' else 'completed' end,
            subtotal = v_subtotal, discount = v_discount_total, total = v_total,
            discount_percent = v_discount_pct, discount_reason = coalesce(p_discount_reason, ''),
            discount_authorized_by = v_authorized_by,
            notes = coalesce(p_notes, ''), prescription_id = p_prescription_id,
            frame_measurements = coalesce(p_frame_measurements, '{}'::jsonb),
            idempotency_key = coalesce(p_idempotency_key, idempotency_key),
            converted_at = case when p_as_quote then null else now() end,
            seller_id = coalesce(p_seller_id, seller_id, v_user),
            updated_at = now()
        where id = v_order_id;
    else
        v_order_number := (case when p_as_quote then 'O-' else 'V-' end)
            || to_char(v_now_local, 'YYYYMMDD-HH24MISS') || '-' || upper(substr(replace(gen_random_uuid()::text, '-', ''), 1, 4));
        insert into public.sales_orders (
            organization_id, customer_id, order_number, status, subtotal, discount, total,
            discount_percent, discount_reason, discount_authorized_by, payment_method, notes,
            prescription_id, frame_measurements, idempotency_key, quoted_at, seller_id, created_by
        ) values (
            p_organization_id, p_customer_id, v_order_number,
            case when p_as_quote then 'draft' else 'completed' end,
            v_subtotal, v_discount_total, v_total, v_discount_pct, coalesce(p_discount_reason, ''),
            v_authorized_by, '', coalesce(p_notes, ''), p_prescription_id,
            coalesce(p_frame_measurements, '{}'::jsonb), p_idempotency_key,
            case when p_as_quote then now() else null end, v_seller, v_user
        ) returning id into v_order_id;
    end if;

    -- Itens: custo congelado; baixa de estoque com histórico somente na venda.
    for v_item in select value from jsonb_array_elements(p_items) loop
        v_qty := (v_item->>'quantity')::numeric;
        v_price := (v_item->>'unit_price')::numeric;
        v_discount := coalesce((v_item->>'discount')::numeric, 0);
        if p_as_quote then
            select * into v_product from public.products
            where id = (v_item->>'product_id')::uuid and organization_id = p_organization_id and active = true;
        else
            select * into v_product from public.products
            where id = (v_item->>'product_id')::uuid and organization_id = p_organization_id and active = true
            for update;
        end if;
        if not found then raise exception 'Produto não encontrado ou inativo.'; end if;

        if not p_as_quote and v_product.tracks_stock then
            if v_product.stock_quantity < v_qty then
                raise exception 'Estoque insuficiente para o produto: % (disponível: %).', v_product.name, v_product.stock_quantity;
            end if;
            update public.products set stock_quantity = stock_quantity - v_qty::integer, updated_at = now()
            where id = v_product.id and organization_id = p_organization_id;
            insert into public.stock_movements (
                organization_id, product_id, movement_type, quantity, previous_quantity,
                resulting_quantity, reason, reference, created_by
            ) values (
                p_organization_id, v_product.id, 'saida', v_qty::integer, v_product.stock_quantity,
                v_product.stock_quantity - v_qty::integer, 'Venda ' || v_order_number, v_order_number, v_user
            );
        end if;

        insert into public.sales_order_items (
            organization_id, sales_order_id, product_id, product_name, sku, quantity,
            unit_price, discount, line_total, unit_cost, product_type
        ) values (
            p_organization_id, v_order_id, v_product.id, v_product.name, coalesce(v_product.sku, ''),
            v_qty, v_price, v_discount, v_qty * v_price - v_discount, v_product.cost_price, v_product.product_type
        );
    end loop;

    if p_as_quote then
        return jsonb_build_object('id', v_order_id, 'order_number', v_order_number, 'status', 'draft',
            'total', v_total, 'discount_percent', v_discount_pct);
    end if;

    -- Pagamentos e financeiro: à vista (inclui cartão parcelado) = recebido; crediário/boleto = a receber.
    for v_payment in select value from jsonb_array_elements(p_payments) loop
        v_method := v_payment->>'method';
        v_amount := round((v_payment->>'amount')::numeric, 2);
        v_installments := coalesce((v_payment->>'installments')::integer, 1);
        v_receivable := v_method in ('crediario', 'boleto');
        v_first_due := coalesce((v_payment->>'first_due_date')::date, current_date + 30);
        v_method_label := case v_method
            when 'dinheiro' then 'Dinheiro' when 'pix' then 'Pix' when 'debito' then 'Cartão de débito'
            when 'credito' then 'Cartão de crédito' when 'transferencia' then 'Transferência'
            when 'crediario' then 'Crediário' when 'boleto' then 'Boleto' else 'Outro' end;
        v_payment_summary := v_payment_summary
            || case when v_payment_summary = '' then '' else ' + ' end
            || v_method_label || case when v_installments > 1 then ' ' || v_installments || 'x' else '' end;

        insert into public.sales_order_payments (
            organization_id, sales_order_id, method, amount, installments, is_down_payment, receivable, first_due_date
        ) values (
            p_organization_id, v_order_id, v_method, v_amount, v_installments,
            coalesce((v_payment->>'is_down_payment')::boolean, false), v_receivable,
            case when v_receivable then v_first_due else null end
        );

        if v_receivable then
            v_part := round(v_amount / v_installments, 2);
            for v_i in 1..v_installments loop
                insert into public.financial_entries (
                    organization_id, direction, category, description, amount, due_date, status,
                    paid_at, payment_method, counterparty, reference, notes, created_by, sales_order_id
                ) values (
                    p_organization_id, 'entrada', 'Vendas',
                    'Venda ' || v_order_number || case when v_installments > 1 then ' — parcela ' || v_i || '/' || v_installments else '' end,
                    case when v_i = v_installments then v_amount - v_part * (v_installments - 1) else v_part end,
                    (v_first_due + make_interval(months => v_i - 1))::date, 'pendente', null,
                    v_method_label, coalesce(v_customer_name, 'Venda avulsa'), v_order_number, '', v_user, v_order_id
                );
            end loop;
        else
            insert into public.financial_entries (
                organization_id, direction, category, description, amount, due_date, status,
                paid_at, payment_method, counterparty, reference, notes, created_by, sales_order_id
            ) values (
                p_organization_id, 'entrada', 'Vendas',
                'Venda ' || v_order_number
                    || case when coalesce((v_payment->>'is_down_payment')::boolean, false) then ' — sinal' else '' end
                    || case when v_installments > 1 then ' — ' || v_method_label || ' ' || v_installments || 'x' else '' end,
                v_amount, current_date, 'pago', current_date, v_method_label,
                coalesce(v_customer_name, 'Venda avulsa'), v_order_number, '', v_user, v_order_id
            );
        end if;
    end loop;

    update public.sales_orders set payment_method = v_payment_summary where id = v_order_id;

    -- Pedido de laboratório criado na mesma transação.
    if p_create_lab_order then
        if p_customer_id is null then
            raise exception 'O pedido exige um cliente identificado.';
        end if;
        if coalesce(p_order_status, '') not in (
            'aguardando_envio', 'enviado_laboratorio', 'em_producao', 'recebido',
            'em_conferencia', 'pronto_retirada', 'entregue'
        ) then
            raise exception 'Status do pedido inválido.';
        end if;
        insert into public.customer_orders (
            organization_id, customer_id, order_number, description, status, expected_at, notes,
            created_by, sales_order_id, prescription_id, frame_measurements, lens_description
        ) values (
            p_organization_id, p_customer_id, v_order_number,
            coalesce(nullif(trim(p_lens_description), ''), 'Pedido da venda ' || v_order_number),
            p_order_status, p_lab_expected_at, '', v_user, v_order_id, p_prescription_id,
            coalesce(p_frame_measurements, '{}'::jsonb), coalesce(p_lens_description, '')
        ) returning id into v_lab_order_id;
    end if;

    return jsonb_build_object('id', v_order_id, 'order_number', v_order_number, 'status', 'completed',
        'total', v_total, 'discount_percent', v_discount_pct, 'lab_order_id', v_lab_order_id,
        'order_status', case when v_lab_order_id is null then null else p_order_status end);
end;
$function$;

revoke all on function public.finalize_sales_order_v2(uuid, uuid, jsonb, jsonb, text, text, uuid, jsonb, uuid, boolean, uuid, boolean, date, text, text, uuid) from public, anon;
grant execute on function public.finalize_sales_order_v2(uuid, uuid, jsonb, jsonb, text, text, uuid, jsonb, uuid, boolean, uuid, boolean, date, text, text, uuid) to authenticated;
