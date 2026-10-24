create table if not exists public.customer_order_events (
 id uuid primary key default gen_random_uuid(),
 organization_id uuid not null references public.organizations(id) on delete cascade,
 customer_id uuid not null,
 order_id uuid not null,
 previous_status text not null default '',
 new_status text not null check (new_status in ('em_desenvolvimento','pronto','entregue','cancelado')),
 changed_by uuid references auth.users(id) on delete set null,
 changed_at timestamptz not null default now(),
 note text not null default '',
 foreign key (customer_id, organization_id) references public.customers(id, organization_id) on delete cascade,
 foreign key (order_id, organization_id) references public.customer_orders(id, organization_id) on delete cascade
);
create index if not exists customer_order_events_timeline_idx on public.customer_order_events (organization_id, order_id, changed_at desc);
alter table public.customer_order_events enable row level security;
drop policy if exists customer_order_events_select_org_member on public.customer_order_events;
create policy customer_order_events_select_org_member on public.customer_order_events for select to authenticated using (exists (select 1 from public.organization_members om where om.organization_id=customer_order_events.organization_id and om.user_id=(select auth.uid()) and om.active=true));
drop policy if exists customer_order_events_insert_org_member on public.customer_order_events;
create policy customer_order_events_insert_org_member on public.customer_order_events for insert to authenticated with check (exists (select 1 from public.organization_members om where om.organization_id=customer_order_events.organization_id and om.user_id=(select auth.uid()) and om.active=true) and exists (select 1 from public.customer_orders o where o.id=customer_order_events.order_id and o.organization_id=customer_order_events.organization_id and o.customer_id=customer_order_events.customer_id));
grant select, insert on public.customer_order_events to authenticated;
revoke all on public.customer_order_events from anon;

create table if not exists public.customer_notification_outbox (
 id uuid primary key default gen_random_uuid(),
 organization_id uuid not null references public.organizations(id) on delete cascade,
 customer_id uuid not null,
 order_id uuid,
 channel text not null check (channel in ('email','whatsapp')),
 event_type text not null check (event_type in ('order_em_desenvolvimento','order_pronto','order_entregue','order_cancelado')),
 recipient text not null,
 subject text not null default '',
 message_body text not null default '',
 status text not null default 'pending' check (status in ('pending','processing','sent','failed','cancelled')),
 attempts integer not null default 0 check (attempts >= 0),
 last_error text not null default '',
 created_at timestamptz not null default now(),
 processed_at timestamptz,
 foreign key (customer_id, organization_id) references public.customers(id, organization_id) on delete cascade,
 foreign key (order_id, organization_id) references public.customer_orders(id, organization_id) on delete set null
);
create index if not exists customer_notification_outbox_pending_idx on public.customer_notification_outbox (created_at) where status='pending';
create index if not exists customer_notification_outbox_org_idx on public.customer_notification_outbox (organization_id, status, created_at desc);
alter table public.customer_notification_outbox enable row level security;
drop policy if exists customer_notification_outbox_select_org_member on public.customer_notification_outbox;
create policy customer_notification_outbox_select_org_member on public.customer_notification_outbox for select to authenticated using (exists (select 1 from public.organization_members om where om.organization_id=customer_notification_outbox.organization_id and om.user_id=(select auth.uid()) and om.active=true));
drop policy if exists customer_notification_outbox_insert_org_member on public.customer_notification_outbox;
create policy customer_notification_outbox_insert_org_member on public.customer_notification_outbox for insert to authenticated with check (exists (select 1 from public.organization_members om where om.organization_id=customer_notification_outbox.organization_id and om.user_id=(select auth.uid()) and om.active=true) and exists (select 1 from public.customers c where c.id=customer_notification_outbox.customer_id and c.organization_id=customer_notification_outbox.organization_id));
grant select, insert on public.customer_notification_outbox to authenticated;
revoke all on public.customer_notification_outbox from anon;