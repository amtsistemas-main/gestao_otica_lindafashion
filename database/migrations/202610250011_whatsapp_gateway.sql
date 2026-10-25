-- WhatsApp via gateway (Evolution API hospedada pela AMT) — uma instância por organização.
-- O cliente final só conecta por QR Code; URL e chave do gateway ficam nos segredos das
-- Edge Functions. Esta migration também corrige a fila de mensagens:
--   * número no formato internacional (55 + DDD + número);
--   * sem mensagens duplicadas por pedido/evento (dedupe_key);
--   * mensagens travadas em "processing" voltam a ser processadas;
--   * inserção na fila somente pela função validada (não mais por INSERT direto);
--   * anexos (PDF) guardados em bucket privado.

-- 1. Conexão de cada organização (leitura pela equipe; escrita só pelas Edge Functions).
create table if not exists public.whatsapp_connections (
    organization_id uuid primary key references public.organizations(id) on delete cascade,
    provider text not null default 'evolution' check (provider in ('evolution', 'meta_cloud')),
    channel text not null default 'baileys' check (channel in ('baileys', 'cloud_api')),
    instance_name text not null unique,
    status text not null default 'disconnected' check (status in ('disconnected', 'connecting', 'connected')),
    phone_number text not null default '',
    profile_name text not null default '',
    connected_at timestamptz,
    last_error text not null default '',
    updated_at timestamptz not null default now()
);
alter table public.whatsapp_connections enable row level security;
drop policy if exists whatsapp_connections_member_read on public.whatsapp_connections;
create policy whatsapp_connections_member_read on public.whatsapp_connections for select to authenticated
using (public.is_org_member(organization_id));
revoke all on public.whatsapp_connections from anon, authenticated;
grant select on public.whatsapp_connections to authenticated;

-- Segredos por instância (webhook): nenhum acesso pela API pública; só a service role.
create table if not exists public.whatsapp_instance_secrets (
    organization_id uuid primary key references public.organizations(id) on delete cascade,
    webhook_secret text not null,
    instance_token text not null default '',
    updated_at timestamptz not null default now()
);
alter table public.whatsapp_instance_secrets enable row level security;
revoke all on public.whatsapp_instance_secrets from anon, authenticated;

-- 2. Número de WhatsApp no formato internacional brasileiro (somente dígitos).
create or replace function public.normalize_br_whatsapp(p_raw text)
returns text
language sql
immutable
set search_path = public, pg_temp
as $$
    with digits as (
        select ltrim(regexp_replace(coalesce(p_raw, ''), '[^0-9]', '', 'g'), '0') as d
    )
    select case
        when length(d) in (10, 11) then '55' || d
        when length(d) in (12, 13) and d like '55%' then d
        when length(d) between 12 and 15 then d
        else ''
    end
    from digits;
$$;

-- 3. Fila: anexos, provedor, deduplicação e mensagens sem cliente (ex.: venda avulsa).
alter table public.customer_notification_outbox
    add column if not exists provider text not null default '',
    add column if not exists attachment_path text not null default '',
    add column if not exists attachment_name text not null default '',
    add column if not exists dedupe_key text,
    add column if not exists created_by uuid references auth.users(id) on delete set null;
alter table public.customer_notification_outbox alter column customer_id drop not null;

alter table public.customer_notification_outbox drop constraint if exists customer_notification_outbox_event_type_check;
alter table public.customer_notification_outbox add constraint customer_notification_outbox_event_type_check check (event_type in (
    'order_aguardando_envio', 'order_enviado_laboratorio', 'order_em_producao', 'order_recebido',
    'order_em_conferencia', 'order_pronto_retirada', 'order_entregue', 'order_cancelado',
    'sales_document', 'crm_message', 'sales_message'
));

create unique index if not exists customer_notification_outbox_dedupe_uidx
    on public.customer_notification_outbox (organization_id, dedupe_key) where dedupe_key is not null;

-- O índice da migration 011 nunca foi recriado (mesmo nome); este cobre o que o worker consulta.
drop index if exists public.customer_notification_outbox_pending_idx;
create index if not exists customer_notification_outbox_due_idx
    on public.customer_notification_outbox (next_attempt_at)
    where channel = 'whatsapp' and status in ('pending', 'retry', 'processing');

-- Destinatários já gravados passam ao formato internacional.
update public.customer_notification_outbox
set recipient = public.normalize_br_whatsapp(recipient)
where channel = 'whatsapp' and status in ('pending', 'retry')
  and public.normalize_br_whatsapp(recipient) <> '' and recipient <> public.normalize_br_whatsapp(recipient);

-- Somente leitura direta pela equipe; inserir passa pela função validada abaixo.
drop policy if exists customer_notification_outbox_insert_org_member on public.customer_notification_outbox;
revoke insert, update, delete on public.customer_notification_outbox from authenticated, anon;

-- 4. Worker: recupera também mensagens travadas em "processing" há mais de 10 minutos.
create or replace function public.claim_customer_whatsapp_outbox(p_batch_size integer default 10)
returns setof public.customer_notification_outbox
language sql
security definer
set search_path = public, pg_temp
as $$
  with picked as (
    select id
    from public.customer_notification_outbox
    where channel = 'whatsapp'
      and (
        (status in ('pending', 'retry') and next_attempt_at <= now())
        or (status = 'processing' and locked_at < now() - interval '10 minutes')
      )
    order by created_at
    for update skip locked
    limit greatest(1, least(coalesce(p_batch_size, 10), 50))
  )
  update public.customer_notification_outbox o
  set status = 'processing', locked_at = now(), attempts = o.attempts + 1, last_error = ''
  from picked
  where o.id = picked.id
  returning o.*;
$$;

-- Envio imediato de uma mensagem específica (botões do app), com a mesma trava do worker.
create or replace function public.claim_customer_whatsapp_outbox_item(p_id uuid)
returns setof public.customer_notification_outbox
language sql
security definer
set search_path = public, pg_temp
as $$
  update public.customer_notification_outbox o
  set status = 'processing', locked_at = now(), attempts = o.attempts + 1, last_error = ''
  where o.id = (
    select id from public.customer_notification_outbox
    where id = p_id and channel = 'whatsapp' and status in ('pending', 'retry')
    for update skip locked
  )
  returning o.*;
$$;

revoke all on function public.claim_customer_whatsapp_outbox(integer) from public, anon, authenticated;
revoke all on function public.claim_customer_whatsapp_outbox_item(uuid) from public, anon, authenticated;
grant execute on function public.claim_customer_whatsapp_outbox(integer) to service_role;
grant execute on function public.claim_customer_whatsapp_outbox_item(uuid) to service_role;

-- 5. Fila automática dos pedidos: número internacional e no máximo uma mensagem por pedido/etapa.
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

  insert into public.customer_notification_outbox
    (organization_id, customer_id, order_id, channel, event_type, recipient, message_body, status, dedupe_key)
  values
    (new.organization_id, new.customer_id, new.id, 'whatsapp', v_event_type, v_recipient, v_body, 'pending',
     'order:' || new.id || ':' || new.status)
  on conflict (organization_id, dedupe_key) where dedupe_key is not null do nothing;
  return new;
end;
$$;
revoke all on function public.enqueue_customer_order_whatsapp() from public, anon, authenticated;

-- 6. Mensagens enviadas pelo app (documento da venda, CRM, contato da venda).
create or replace function public.enqueue_whatsapp_message(
    p_organization_id uuid,
    p_customer_id uuid,
    p_recipient text,
    p_message text,
    p_event_type text,
    p_attachment_path text default '',
    p_attachment_name text default '',
    p_dedupe_key text default null
) returns uuid
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
    v_recipient text := public.normalize_br_whatsapp(p_recipient);
    v_module text;
    v_id uuid;
begin
    if auth.uid() is null or not public.is_org_member(p_organization_id) then
        raise exception 'Usuário sem vínculo ativo com esta organização.';
    end if;
    if p_event_type not in ('sales_document', 'sales_message', 'crm_message') then
        raise exception 'Tipo de mensagem inválido.';
    end if;
    v_module := case when p_event_type = 'crm_message' then 'relacionamento' else 'vendas' end;
    if not public.has_module_access(p_organization_id, v_module) then
        raise exception 'Seu usuário não tem acesso a este módulo.';
    end if;
    if v_recipient = '' then
        raise exception 'Número de WhatsApp inválido. Informe DDD e número.';
    end if;
    if coalesce(trim(p_message), '') = '' and coalesce(p_attachment_path, '') = '' then
        raise exception 'A mensagem está vazia.';
    end if;
    if length(coalesce(p_message, '')) > 4000 then
        raise exception 'A mensagem pode ter no máximo 4000 caracteres.';
    end if;
    if coalesce(p_attachment_path, '') <> ''
       and split_part(p_attachment_path, '/', 1) <> p_organization_id::text then
        raise exception 'Anexo inválido para esta organização.';
    end if;
    if p_customer_id is not null then
        if not exists (select 1 from public.customers c where c.id = p_customer_id and c.organization_id = p_organization_id) then
            raise exception 'Cliente inválido para esta organização.';
        end if;
        -- Mensagens de relacionamento exigem consentimento; o documento da venda é solicitado
        -- pelo próprio cliente no atendimento (o app pede confirmação antes de enviar).
        if p_event_type = 'crm_message' and not exists (
            select 1 from public.customers c where c.id = p_customer_id and c.whatsapp_consent = true
        ) then
            raise exception 'O cliente não autorizou contato por WhatsApp.';
        end if;
    end if;

    insert into public.customer_notification_outbox (
        organization_id, customer_id, channel, event_type, recipient, message_body,
        attachment_path, attachment_name, dedupe_key, status, created_by
    ) values (
        p_organization_id, p_customer_id, 'whatsapp', p_event_type, v_recipient, coalesce(p_message, ''),
        coalesce(p_attachment_path, ''), left(coalesce(p_attachment_name, ''), 200), p_dedupe_key, 'pending', auth.uid()
    )
    on conflict (organization_id, dedupe_key) where dedupe_key is not null do nothing
    returning id into v_id;

    if v_id is null then
        select id into v_id from public.customer_notification_outbox
        where organization_id = p_organization_id and dedupe_key = p_dedupe_key;
    end if;
    return v_id;
end;
$$;
revoke all on function public.enqueue_whatsapp_message(uuid, uuid, text, text, text, text, text, text) from public, anon;
grant execute on function public.enqueue_whatsapp_message(uuid, uuid, text, text, text, text, text, text) to authenticated;

-- 7. Bucket privado para os documentos enviados (pasta = organização).
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('whatsapp-documents', 'whatsapp-documents', false, 10485760, array['application/pdf'])
on conflict (id) do update set public = false, file_size_limit = excluded.file_size_limit,
    allowed_mime_types = excluded.allowed_mime_types;

drop policy if exists whatsapp_documents_member_insert on storage.objects;
create policy whatsapp_documents_member_insert on storage.objects for insert to authenticated
with check (
    bucket_id = 'whatsapp-documents'
    and (storage.foldername(name))[1] in (
        select m.organization_id::text from public.organization_members m
        where m.user_id = (select auth.uid()) and m.active = true
    )
);
drop policy if exists whatsapp_documents_member_read on storage.objects;
create policy whatsapp_documents_member_read on storage.objects for select to authenticated
using (
    bucket_id = 'whatsapp-documents'
    and (storage.foldername(name))[1] in (
        select m.organization_id::text from public.organization_members m
        where m.user_id = (select auth.uid()) and m.active = true
    )
);

comment on table public.whatsapp_connections is 'Conexão WhatsApp de cada organização (gateway Evolution); escrita somente pelas Edge Functions.';
comment on function public.normalize_br_whatsapp(text) is 'Número de WhatsApp em dígitos no formato internacional (55 + DDD + número) ou vazio se inválido.';
