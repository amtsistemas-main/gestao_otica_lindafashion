-- Configurable WhatsApp templates and automatic queueing when order status changes.
create table if not exists public.customer_whatsapp_templates (
 id uuid primary key default gen_random_uuid(),
 organization_id uuid not null references public.organizations(id) on delete cascade,
 event_type text not null check (event_type in ('order_em_desenvolvimento','order_pronto','order_entregue','order_cancelado')),
 message_body text not null,
 enabled boolean not null default true,
 updated_by uuid references auth.users(id) on delete set null,
 created_at timestamptz not null default now(),
 updated_at timestamptz not null default now(),
 unique (organization_id, event_type)
);
alter table public.customer_whatsapp_templates enable row level security;
drop policy if exists customer_whatsapp_templates_select_org_member on public.customer_whatsapp_templates;
create policy customer_whatsapp_templates_select_org_member on public.customer_whatsapp_templates for select to authenticated using (exists (select 1 from public.organization_members om where om.organization_id=customer_whatsapp_templates.organization_id and om.user_id=(select auth.uid()) and om.active=true));
drop policy if exists customer_whatsapp_templates_insert_org_member on public.customer_whatsapp_templates;
create policy customer_whatsapp_templates_insert_org_member on public.customer_whatsapp_templates for insert to authenticated with check (exists (select 1 from public.organization_members om where om.organization_id=customer_whatsapp_templates.organization_id and om.user_id=(select auth.uid()) and om.active=true));
drop policy if exists customer_whatsapp_templates_update_org_member on public.customer_whatsapp_templates;
create policy customer_whatsapp_templates_update_org_member on public.customer_whatsapp_templates for update to authenticated using (exists (select 1 from public.organization_members om where om.organization_id=customer_whatsapp_templates.organization_id and om.user_id=(select auth.uid()) and om.active=true)) with check (exists (select 1 from public.organization_members om where om.organization_id=customer_whatsapp_templates.organization_id and om.user_id=(select auth.uid()) and om.active=true));
grant select, insert, update on public.customer_whatsapp_templates to authenticated;
revoke all on public.customer_whatsapp_templates from anon;

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
begin
  if tg_op = 'UPDATE' and new.status is not distinct from old.status then
    return new;
  end if;

  v_event_type := case new.status
    when 'em_desenvolvimento' then 'order_em_desenvolvimento'
    when 'pronto' then 'order_pronto'
    when 'entregue' then 'order_entregue'
    when 'cancelado' then 'order_cancelado'
    else null
  end;
  if v_event_type is null then return new; end if;

  select * into v_customer
  from public.customers c
  where c.id = new.customer_id
    and c.organization_id = new.organization_id
    and c.active = true
    and c.whatsapp_consent = true
    and coalesce(nullif(trim(c.whatsapp), ''), '') <> ''
  limit 1;
  if not found then return new; end if;

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
  v_body := replace(v_body, '{{status}}', case new.status when 'em_desenvolvimento' then 'Em desenvolvimento' when 'pronto' then 'Óculos pronto' when 'entregue' then 'Entregue' when 'cancelado' then 'Cancelado' else new.status end);
  v_body := replace(v_body, '{{previsao}}', coalesce(to_char(new.expected_at, 'DD/MM/YYYY'), 'a confirmar'));

  insert into public.customer_notification_outbox
    (organization_id, customer_id, order_id, channel, event_type, recipient, message_body, status)
  values
    (new.organization_id, new.customer_id, new.id, 'whatsapp', v_event_type, regexp_replace(v_customer.whatsapp, '\\D', '', 'g'), v_body, 'pending');
  return new;
end;
$$;

drop trigger if exists customer_order_whatsapp_enqueue on public.customer_orders;
create trigger customer_order_whatsapp_enqueue
after insert or update of status on public.customer_orders
for each row execute function public.enqueue_customer_order_whatsapp();
