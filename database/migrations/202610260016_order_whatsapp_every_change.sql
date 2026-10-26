-- Mensagens de status do pedido: uma por mudança de status.
--
-- Defeito: a chave de deduplicação era 'order:<pedido>:<status>'. Quando o pedido voltava
-- para uma etapa já avisada (ex.: em produção -> enviado -> em produção), o insert caía no
-- ON CONFLICT DO NOTHING e a mensagem era descartada em silêncio.
-- Correção: a chave inclui a transação (txid_current()); cada mudança confirmada gera sua
-- mensagem, e a mesma transação continua sem duplicar.

create or replace function public.enqueue_customer_order_whatsapp()
returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  v_customer public.customers%rowtype;
  v_template public.customer_whatsapp_templates%rowtype;
  v_event_type text;
  v_body text;
  v_status_label text;
  v_recipient text;
  v_store text;
begin
  if tg_op = 'UPDATE' and new.status is not distinct from old.status then
    return new;
  end if;

  v_event_type := 'order_' || new.status;
  v_status_label := case new.status
    when 'aguardando_envio' then 'Aguardando envio'
    when 'enviado_laboratorio' then 'Enviado ao laboratório'
    when 'em_producao' then 'Em produção'
    when 'recebido' then 'Recebido do laboratório'
    when 'em_conferencia' then 'Em conferência'
    when 'pronto_retirada' then 'Pronto para retirada'
    when 'entregue' then 'Entregue'
    when 'cancelado' then 'Cancelado'
    else new.status end;

  select * into v_customer
  from public.customers c
  where c.id = new.customer_id
    and c.organization_id = new.organization_id
    and c.active = true
    and c.whatsapp_consent = true
  limit 1;
  if not found then return new; end if;
  v_recipient := public.normalize_br_whatsapp(v_customer.whatsapp);
  if v_recipient = '' then return new; end if;

  select * into v_template
  from public.customer_whatsapp_templates t
  where t.organization_id = new.organization_id
    and t.event_type = v_event_type
    and t.enabled = true
  limit 1;
  if not found then return new; end if;

  v_body := v_template.message_body;
  v_body := replace(v_body, '{{cliente}}', coalesce(v_customer.full_name, ''));
  v_body := replace(v_body, '{{pedido}}', coalesce(nullif(new.order_number, ''), 'não informado'));
  v_body := replace(v_body, '{{descricao}}', coalesce(new.description, ''));
  v_body := replace(v_body, '{{status}}', v_status_label);
  v_body := replace(v_body, '{{previsao}}', coalesce(to_char(new.expected_at, 'DD/MM/YYYY'), 'a confirmar'));
  select coalesce(nullif(s.store_name, ''), o.name) into v_store
  from public.organizations o
  left join public.organization_settings s on s.organization_id = o.id
  where o.id = new.organization_id;
  v_body := replace(v_body, '{{loja}}', coalesce(v_store, ''));

  insert into public.customer_notification_outbox
    (organization_id, customer_id, order_id, channel, event_type, recipient, message_body, status, dedupe_key)
  values
    (new.organization_id, new.customer_id, new.id, 'whatsapp', v_event_type, v_recipient, v_body, 'pending',
     'order:' || new.id || ':' || new.status || ':' || txid_current()::text)
  on conflict (organization_id, dedupe_key) where dedupe_key is not null do nothing;
  return new;
end;
$$;
