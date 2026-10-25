-- WhatsApp: envio validado pelo cadastro do cliente e agendamento do worker.
--
-- 1. enqueue_whatsapp_message passa a usar SEMPRE o número do cadastro quando há cliente
--    (o app não escolhe destinatário livre). Número digitado só é aceito para o documento
--    de uma venda sem cliente (venda avulsa), e há limite de envios por usuário.
-- 2. pg_cron chama o worker a cada minuto, somente quando há mensagens a enviar.
--    URL e segredo do worker ficam no Vault (criados fora do SQL versionado):
--      select vault.create_secret('https://<ref>.supabase.co/functions/v1/process-customer-whatsapp-outbox', 'whatsapp_worker_url');
--      select vault.create_secret('<mesmo valor do secret WHATSAPP_CRON_SECRET>', 'whatsapp_cron_secret');

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
    v_customer public.customers%rowtype;
    v_recipient text;
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
    if coalesce(trim(p_message), '') = '' and coalesce(p_attachment_path, '') = '' then
        raise exception 'A mensagem está vazia.';
    end if;
    if length(coalesce(p_message, '')) > 4000 then
        raise exception 'A mensagem pode ter no máximo 4000 caracteres.';
    end if;
    if coalesce(p_attachment_path, '') <> '' and (
        split_part(p_attachment_path, '/', 1) <> p_organization_id::text
        or lower(p_attachment_path) not like '%.pdf'
    ) then
        raise exception 'Anexo inválido para esta organização.';
    end if;
    if (select count(*) from public.customer_notification_outbox
        where created_by = auth.uid() and created_at > now() - interval '10 minutes') >= 30 then
        raise exception 'Muitos envios em sequência. Aguarde alguns minutos e tente novamente.';
    end if;

    if p_customer_id is not null then
        select * into v_customer from public.customers c
        where c.id = p_customer_id and c.organization_id = p_organization_id;
        if not found then
            raise exception 'Cliente inválido para esta organização.';
        end if;
        -- Relacionamento exige consentimento; documento/contato da venda é pedido pelo próprio
        -- cliente no atendimento (o app confirma antes de enviar).
        if p_event_type = 'crm_message' and not v_customer.whatsapp_consent then
            raise exception 'O cliente não autorizou contato por WhatsApp.';
        end if;
        v_recipient := public.normalize_br_whatsapp(v_customer.whatsapp);
        if v_recipient = '' then
            v_recipient := public.normalize_br_whatsapp(v_customer.phone);
        end if;
        if v_recipient = '' then
            raise exception 'O cliente não tem WhatsApp válido no cadastro.';
        end if;
    else
        if p_event_type <> 'sales_document' or coalesce(p_attachment_path, '') = '' then
            raise exception 'Envio sem cliente só é permitido para o documento da venda.';
        end if;
        v_recipient := public.normalize_br_whatsapp(p_recipient);
        if v_recipient = '' then
            raise exception 'Número de WhatsApp inválido. Informe DDD e número.';
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

-- Worker agendado.
create extension if not exists pg_cron;
create extension if not exists pg_net with schema extensions;

create or replace function public.run_whatsapp_worker()
returns void
language plpgsql
security definer
set search_path = public, extensions, pg_temp
as $$
declare
    v_url text;
    v_secret text;
begin
    -- Sem mensagens vencidas, nada é chamado (não gasta invocações da Edge Function).
    if not exists (
        select 1 from public.customer_notification_outbox
        where channel = 'whatsapp'
          and ((status in ('pending', 'retry') and next_attempt_at <= now())
               or (status = 'processing' and locked_at < now() - interval '10 minutes'))
    ) then
        return;
    end if;
    select decrypted_secret into v_url from vault.decrypted_secrets where name = 'whatsapp_worker_url';
    select decrypted_secret into v_secret from vault.decrypted_secrets where name = 'whatsapp_cron_secret';
    if v_url is null or v_secret is null then
        return;
    end if;
    perform net.http_post(
        url := v_url,
        headers := jsonb_build_object('Content-Type', 'application/json', 'x-cron-secret', v_secret),
        body := '{}'::jsonb,
        timeout_milliseconds := 10000
    );
end;
$$;
revoke all on function public.run_whatsapp_worker() from public, anon, authenticated;

do $$
begin
    if exists (select 1 from cron.job where jobname = 'whatsapp-outbox-worker') then
        perform cron.unschedule('whatsapp-outbox-worker');
    end if;
    perform cron.schedule('whatsapp-outbox-worker', '* * * * *', 'select public.run_whatsapp_worker()');
end $$;
