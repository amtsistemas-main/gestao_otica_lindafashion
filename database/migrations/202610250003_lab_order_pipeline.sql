-- Fase 3 — Gestão completa de pedidos e laboratório.
-- Fluxo: aguardando_envio → enviado_laboratorio → em_producao → recebido → em_conferencia
--        → pronto_retirada → entregue (ou cancelado), com prazos, custos e ocorrências.

-- 0. Garantias estruturais usadas pelas chaves compostas.
create unique index if not exists customer_orders_id_org_unique
    on public.customer_orders (id, organization_id);

-- 1. Remove as restrições antigas de status antes de converter os dados.
alter table public.customer_orders drop constraint if exists customer_orders_status_check;
alter table public.customer_order_events drop constraint if exists customer_order_events_new_status_check;
alter table public.customer_interactions drop constraint if exists customer_interactions_order_status_check;
alter table public.customer_notification_outbox drop constraint if exists customer_notification_outbox_event_type_check;
alter table public.customer_whatsapp_templates drop constraint if exists customer_whatsapp_templates_event_type_check;

-- 2. Converte os status antigos sem gerar eventos nem mensagens durante a migração.
alter table public.customer_orders disable trigger customer_order_status_event_after_write;
alter table public.customer_orders disable trigger customer_order_whatsapp_enqueue;

update public.customer_orders
set status = case status when 'em_desenvolvimento' then 'em_producao' when 'pronto' then 'pronto_retirada' else status end
where status in ('em_desenvolvimento', 'pronto');

alter table public.customer_orders enable trigger customer_order_status_event_after_write;
alter table public.customer_orders enable trigger customer_order_whatsapp_enqueue;

update public.customer_order_events
set new_status = case new_status when 'em_desenvolvimento' then 'em_producao' when 'pronto' then 'pronto_retirada' else new_status end,
    previous_status = case previous_status when 'em_desenvolvimento' then 'em_producao' when 'pronto' then 'pronto_retirada' else previous_status end
where new_status in ('em_desenvolvimento', 'pronto') or previous_status in ('em_desenvolvimento', 'pronto');

update public.customer_interactions
set order_status = case order_status when 'em_desenvolvimento' then 'em_producao' when 'pronto' then 'pronto_retirada' else order_status end
where order_status in ('em_desenvolvimento', 'pronto');

update public.customer_notification_outbox
set event_type = case event_type when 'order_em_desenvolvimento' then 'order_em_producao' when 'order_pronto' then 'order_pronto_retirada' else event_type end
where event_type in ('order_em_desenvolvimento', 'order_pronto');

update public.customer_whatsapp_templates
set event_type = case event_type when 'order_em_desenvolvimento' then 'order_em_producao' when 'order_pronto' then 'order_pronto_retirada' else event_type end
where event_type in ('order_em_desenvolvimento', 'order_pronto');

-- 3. Novas restrições com o fluxo completo.
alter table public.customer_orders alter column status set default 'aguardando_envio';
alter table public.customer_orders add constraint customer_orders_status_check check (status in (
    'aguardando_envio','enviado_laboratorio','em_producao','recebido','em_conferencia','pronto_retirada','entregue','cancelado'
));
alter table public.customer_order_events add constraint customer_order_events_new_status_check check (new_status in (
    'aguardando_envio','enviado_laboratorio','em_producao','recebido','em_conferencia','pronto_retirada','entregue','cancelado'
));
alter table public.customer_interactions add constraint customer_interactions_order_status_check check (order_status in (
    '','aguardando_envio','enviado_laboratorio','em_producao','recebido','em_conferencia','pronto_retirada','entregue','cancelado'
));
alter table public.customer_notification_outbox add constraint customer_notification_outbox_event_type_check check (event_type in (
    'order_aguardando_envio','order_enviado_laboratorio','order_em_producao','order_recebido','order_em_conferencia',
    'order_pronto_retirada','order_entregue','order_cancelado'
));
alter table public.customer_whatsapp_templates add constraint customer_whatsapp_templates_event_type_check check (event_type in (
    'order_aguardando_envio','order_enviado_laboratorio','order_em_producao','order_recebido','order_em_conferencia',
    'order_pronto_retirada','order_entregue','order_cancelado'
));

-- 4. Dados de laboratório, prazos, custos e vínculos.
alter table public.customer_orders
    add column if not exists sales_order_id uuid,
    add column if not exists prescription_id uuid,
    add column if not exists laboratory_id uuid,
    add column if not exists lab_order_number text not null default '',
    add column if not exists lab_cost numeric(12,2) not null default 0,
    add column if not exists lab_expected_at date,
    add column if not exists lens_description text not null default '',
    add column if not exists frame_measurements jsonb not null default '{}'::jsonb,
    add column if not exists sent_at timestamptz,
    add column if not exists received_at timestamptz,
    add column if not exists checked_at timestamptz;

alter table public.customer_orders drop constraint if exists customer_orders_lab_cost_check;
alter table public.customer_orders add constraint customer_orders_lab_cost_check check (lab_cost >= 0);

do $$
begin
    if not exists (select 1 from pg_constraint where conname = 'customer_orders_sales_order_org_fk') then
        alter table public.customer_orders add constraint customer_orders_sales_order_org_fk
            foreign key (sales_order_id, organization_id)
            references public.sales_orders (id, organization_id) on delete set null (sales_order_id);
    end if;
    if not exists (select 1 from pg_constraint where conname = 'customer_orders_prescription_org_fk') then
        alter table public.customer_orders add constraint customer_orders_prescription_org_fk
            foreign key (prescription_id, organization_id)
            references public.customer_prescriptions (id, organization_id) on delete set null (prescription_id);
    end if;
    if not exists (select 1 from pg_constraint where conname = 'customer_orders_laboratory_org_fk') then
        alter table public.customer_orders add constraint customer_orders_laboratory_org_fk
            foreign key (laboratory_id, organization_id)
            references public.suppliers (id, organization_id) on delete set null (laboratory_id);
    end if;
end $$;

create index if not exists customer_orders_org_sales_order_idx
    on public.customer_orders (organization_id, sales_order_id) where sales_order_id is not null;
create index if not exists customer_orders_org_lab_idx
    on public.customer_orders (organization_id, laboratory_id, status);

-- 5. Datas de cada etapa preenchidas pelo banco na transição de status.
create or replace function public.stamp_customer_order_stage()
returns trigger
language plpgsql
set search_path = public, pg_temp
as $$
begin
    if tg_op = 'UPDATE' and new.status is not distinct from old.status then
        return new;
    end if;
    new.updated_at := now();
    if new.status = 'enviado_laboratorio' and new.sent_at is null then new.sent_at := now(); end if;
    if new.status = 'recebido' and new.received_at is null then new.received_at := now(); end if;
    if new.status = 'em_conferencia' and new.checked_at is null then new.checked_at := now(); end if;
    if new.status = 'pronto_retirada' and new.completed_at is null then new.completed_at := now(); end if;
    if new.status = 'entregue' and new.delivered_at is null then new.delivered_at := now(); end if;
    return new;
end;
$$;

drop trigger if exists customer_order_stage_stamp on public.customer_orders;
create trigger customer_order_stage_stamp
before insert or update of status on public.customer_orders
for each row execute function public.stamp_customer_order_stage();

-- 6. Ocorrências do pedido (atrasos, erros de laboratório, retrabalho, garantia...).
create table if not exists public.customer_order_occurrences (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null references public.organizations(id) on delete cascade,
    order_id uuid not null,
    occurrence_type text not null default 'outro'
        check (occurrence_type in ('atraso','erro_laboratorio','retrabalho','avaria','garantia','outro')),
    description text not null check (length(trim(description)) > 0),
    cost numeric(12,2) not null default 0 check (cost >= 0),
    resolved_at timestamptz,
    created_by uuid references auth.users(id) on delete set null,
    created_at timestamptz not null default now(),
    constraint customer_order_occurrences_order_org_fk
        foreign key (order_id, organization_id)
        references public.customer_orders (id, organization_id) on delete cascade
);
create index if not exists customer_order_occurrences_order_idx
    on public.customer_order_occurrences (organization_id, order_id, created_at desc);

alter table public.customer_order_occurrences enable row level security;
drop policy if exists customer_order_occurrences_member_all on public.customer_order_occurrences;
create policy customer_order_occurrences_member_all on public.customer_order_occurrences for all to authenticated
using (exists (select 1 from public.organization_members om where om.organization_id = customer_order_occurrences.organization_id and om.user_id = (select auth.uid()) and om.active = true))
with check (exists (select 1 from public.organization_members om where om.organization_id = customer_order_occurrences.organization_id and om.user_id = (select auth.uid()) and om.active = true));
grant select, insert, update on public.customer_order_occurrences to authenticated;
revoke all on public.customer_order_occurrences from anon;

-- 7. Fila automática de WhatsApp com os novos status.
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
    and length(regexp_replace(coalesce(c.whatsapp, ''), '[^0-9]', '', 'g')) >= 10
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
  v_body := replace(v_body, '{{status}}', v_status_label);
  v_body := replace(v_body, '{{previsao}}', coalesce(to_char(new.expected_at, 'DD/MM/YYYY'), 'a confirmar'));

  insert into public.customer_notification_outbox
    (organization_id, customer_id, order_id, channel, event_type, recipient, message_body, status)
  values
    (new.organization_id, new.customer_id, new.id, 'whatsapp', v_event_type,
     regexp_replace(v_customer.whatsapp, '[^0-9]', '', 'g'), v_body, 'pending');
  return new;
end;
$$;

comment on table public.customer_order_occurrences is 'Ocorrências do pedido/laboratório: atrasos, erros, retrabalho, avarias e garantia, com custo.';
