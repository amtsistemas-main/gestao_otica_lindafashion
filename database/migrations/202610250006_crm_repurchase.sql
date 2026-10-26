-- Fase 6 — CRM e recompra inteligente.
-- Preferências do cliente, agenda de relacionamento e tarefas automáticas de pós-venda e
-- revisão de receita, geradas pelo banco sem duplicidade.

alter table public.customers
    add column if not exists preferred_brands text not null default '',
    add column if not exists frame_preferences text not null default '',
    add column if not exists lens_preferences text not null default '',
    add column if not exists preferred_channel text not null default '';

alter table public.customers drop constraint if exists customers_preferred_channel_check;
alter table public.customers add constraint customers_preferred_channel_check
    check (preferred_channel in ('', 'whatsapp', 'email', 'telefone'));

create table if not exists public.crm_tasks (
    id uuid primary key default gen_random_uuid(),
    organization_id uuid not null references public.organizations(id) on delete cascade,
    customer_id uuid not null,
    task_type text not null default 'outro'
        check (task_type in ('pos_venda','revisao_receita','aniversario','reativacao','campanha','outro')),
    title text not null check (length(trim(title)) > 0),
    due_date date not null default current_date,
    status text not null default 'aberta' check (status in ('aberta','concluida','cancelada')),
    related_order_id uuid,
    related_prescription_id uuid,
    notes text not null default '',
    completed_at timestamptz,
    created_by uuid references auth.users(id) on delete set null,
    created_at timestamptz not null default now(),
    constraint crm_tasks_customer_org_fk
        foreign key (customer_id, organization_id)
        references public.customers (id, organization_id) on delete cascade
);

create index if not exists crm_tasks_org_due_idx on public.crm_tasks (organization_id, status, due_date);
create index if not exists crm_tasks_customer_idx on public.crm_tasks (organization_id, customer_id, due_date desc);
create unique index if not exists crm_tasks_order_type_unique
    on public.crm_tasks (organization_id, task_type, related_order_id) where related_order_id is not null;
create unique index if not exists crm_tasks_prescription_type_unique
    on public.crm_tasks (organization_id, task_type, related_prescription_id) where related_prescription_id is not null;

alter table public.crm_tasks enable row level security;
drop policy if exists crm_tasks_member_select on public.crm_tasks;
create policy crm_tasks_member_select on public.crm_tasks for select to authenticated
using (public.is_org_member(organization_id));
drop policy if exists crm_tasks_member_insert on public.crm_tasks;
create policy crm_tasks_member_insert on public.crm_tasks for insert to authenticated
with check (
    public.is_org_member(organization_id)
    and exists (select 1 from public.customers c where c.id = crm_tasks.customer_id and c.organization_id = crm_tasks.organization_id)
);
drop policy if exists crm_tasks_member_update on public.crm_tasks;
create policy crm_tasks_member_update on public.crm_tasks for update to authenticated
using (public.is_org_member(organization_id)) with check (public.is_org_member(organization_id));
grant select, insert, update on public.crm_tasks to authenticated;
revoke all on public.crm_tasks from anon;

-- Pós-venda automático quando o pedido é entregue.
create or replace function public.create_post_sale_followup()
returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
    v_days integer;
begin
    if new.status <> 'entregue' or (tg_op = 'UPDATE' and old.status = 'entregue') then
        return new;
    end if;
    select followup_days_after_delivery into v_days
    from public.organization_settings where organization_id = new.organization_id;
    insert into public.crm_tasks (organization_id, customer_id, task_type, title, due_date, related_order_id, notes)
    values (
        new.organization_id, new.customer_id, 'pos_venda',
        'Pós-venda: adaptação aos óculos' || case when new.order_number <> '' then ' (' || new.order_number || ')' else '' end,
        (coalesce(new.delivered_at, now()) at time zone 'America/Sao_Paulo')::date + coalesce(v_days, 7),
        new.id, 'Confirmar adaptação, conforto e satisfação; oferecer ajuste gratuito se necessário.'
    )
    on conflict (organization_id, task_type, related_order_id) where related_order_id is not null do nothing;
    return new;
end;
$$;

drop trigger if exists customer_order_post_sale_followup on public.customer_orders;
create trigger customer_order_post_sale_followup
after insert or update of status on public.customer_orders
for each row execute function public.create_post_sale_followup();

-- Lembrete de revisão da receita antes do vencimento; a receita nova encerra o lembrete antigo.
create or replace function public.schedule_prescription_review()
returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
    v_months integer;
    v_days_before integer;
    v_expiry date;
begin
    if not new.active then
        return new;
    end if;
    select prescription_validity_months, review_reminder_days_before into v_months, v_days_before
    from public.organization_settings where organization_id = new.organization_id;
    v_expiry := coalesce(new.expires_at, (new.prescribed_at + make_interval(months => coalesce(v_months, 12)))::date);

    if tg_op = 'INSERT' then
        update public.crm_tasks
        set status = 'concluida', completed_at = now(), notes = notes || ' Receita renovada.'
        where organization_id = new.organization_id and customer_id = new.customer_id
          and task_type = 'revisao_receita' and status = 'aberta'
          and related_prescription_id is distinct from new.id;
    end if;

    insert into public.crm_tasks (organization_id, customer_id, task_type, title, due_date, related_prescription_id, notes)
    values (
        new.organization_id, new.customer_id, 'revisao_receita',
        'Revisão da receita (vence em ' || to_char(v_expiry, 'DD/MM/YYYY') || ')',
        greatest(current_date, v_expiry - coalesce(v_days_before, 30)),
        new.id, 'Convidar para novo exame de vista e apresentar lançamentos de armações e lentes.'
    )
    on conflict (organization_id, task_type, related_prescription_id) where related_prescription_id is not null
    do update set due_date = excluded.due_date, title = excluded.title
    where public.crm_tasks.status = 'aberta';
    return new;
end;
$$;

drop trigger if exists customer_prescription_review_reminder on public.customer_prescriptions;
create trigger customer_prescription_review_reminder
after insert or update of prescribed_at, expires_at, active on public.customer_prescriptions
for each row execute function public.schedule_prescription_review();

comment on table public.crm_tasks is 'Agenda de relacionamento: pós-venda, revisão de receita, aniversários, reativação e campanhas.';
