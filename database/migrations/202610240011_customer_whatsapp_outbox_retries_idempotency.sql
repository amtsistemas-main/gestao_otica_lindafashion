-- Harden the WhatsApp outbox for safe claims, retries, and provider status tracking.
alter table public.customer_notification_outbox
  add column if not exists next_attempt_at timestamptz not null default now(),
  add column if not exists locked_at timestamptz,
  add column if not exists provider_message_id text,
  add column if not exists sent_at timestamptz,
  add column if not exists failed_at timestamptz;

create index if not exists customer_notification_outbox_pending_idx
  on public.customer_notification_outbox (next_attempt_at, created_at)
  where status in ('pending','retry');

create unique index if not exists customer_notification_outbox_provider_message_id_uidx
  on public.customer_notification_outbox (provider_message_id)
  where provider_message_id is not null;

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
      and status in ('pending','retry')
      and next_attempt_at <= now()
      and (locked_at is null or locked_at < now() - interval '10 minutes')
    order by created_at
    for update skip locked
    limit greatest(1, least(coalesce(p_batch_size,10),50))
  )
  update public.customer_notification_outbox o
  set status='processing', locked_at=now(), attempts=o.attempts+1, last_error=''
  from picked
  where o.id=picked.id
  returning o.*;
$$;

revoke all on function public.claim_customer_whatsapp_outbox(integer) from public, anon, authenticated;
grant execute on function public.claim_customer_whatsapp_outbox(integer) to service_role;

create or replace function public.complete_customer_whatsapp_outbox(
  p_id uuid, p_provider_message_id text
)
returns boolean
language plpgsql
security definer
set search_path = public, pg_temp
as $$
begin
  update public.customer_notification_outbox
  set status='sent', provider_message_id=p_provider_message_id,
      sent_at=now(), processed_at=now(), locked_at=null, last_error=''
  where id=p_id and status='processing';
  return found;
end;
$$;

create or replace function public.fail_customer_whatsapp_outbox(
  p_id uuid, p_error text, p_retry boolean, p_delay_seconds integer default 60
)
returns boolean
language plpgsql
security definer
set search_path = public, pg_temp
as $$
begin
  update public.customer_notification_outbox
  set status=case when p_retry and attempts < 6 then 'retry' else 'failed' end,
      last_error=left(coalesce(p_error,'Falha desconhecida'),2000),
      next_attempt_at=now()+make_interval(secs=>greatest(30,least(coalesce(p_delay_seconds,60),21600))),
      failed_at=case when not p_retry or attempts >= 6 then now() else null end,
      processed_at=case when not p_retry or attempts >= 6 then now() else null end,
      locked_at=null
  where id=p_id and status='processing';
  return found;
end;
$$;

revoke all on function public.complete_customer_whatsapp_outbox(uuid,text) from public, anon, authenticated;
revoke all on function public.fail_customer_whatsapp_outbox(uuid,text,boolean,integer) from public, anon, authenticated;
grant execute on function public.complete_customer_whatsapp_outbox(uuid,text) to service_role;
grant execute on function public.fail_customer_whatsapp_outbox(uuid,text,boolean,integer) to service_role;
