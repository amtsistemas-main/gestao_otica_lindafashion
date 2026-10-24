-- Keep order status changes and their audit events in the same database transaction.
-- This migration intentionally does not enqueue or send email/WhatsApp notifications.

create or replace function public.capture_customer_order_status_event()
returns trigger
language plpgsql
set search_path = public, pg_temp
as $$
begin
  if tg_op = 'INSERT' then
    insert into public.customer_order_events (
      organization_id, customer_id, order_id, previous_status, new_status, changed_by, note
    ) values (
      new.organization_id, new.customer_id, new.id, '', new.status, auth.uid(), 'Status inicial do pedido'
    );
    return new;
  end if;

  if new.status is distinct from old.status then
    insert into public.customer_order_events (
      organization_id, customer_id, order_id, previous_status, new_status, changed_by, note
    ) values (
      new.organization_id, new.customer_id, new.id, old.status, new.status, auth.uid(), ''
    );
  end if;
  return new;
end;
$$;

drop trigger if exists customer_order_status_event_after_write on public.customer_orders;
create trigger customer_order_status_event_after_write
after insert or update of status on public.customer_orders
for each row
execute function public.capture_customer_order_status_event();
