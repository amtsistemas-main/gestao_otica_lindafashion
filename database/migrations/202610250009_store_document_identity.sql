-- Identificação da loja nos documentos (ordem de serviço, orçamento e comprovante de venda).
-- Fica nas configurações da organização: leitura pela equipe, alteração por dono/administrador
-- (políticas existentes de organization_settings).

alter table public.organization_settings
    add column if not exists store_name text not null default '',
    add column if not exists store_document text not null default '',
    add column if not exists store_phone text not null default '',
    add column if not exists store_whatsapp text not null default '',
    add column if not exists store_email text not null default '',
    add column if not exists store_address text not null default '',
    add column if not exists store_website text not null default '',
    add column if not exists quote_validity_days integer not null default 7,
    add column if not exists document_terms text not null default '';

alter table public.organization_settings drop constraint if exists organization_settings_quote_validity_check;
alter table public.organization_settings add constraint organization_settings_quote_validity_check
    check (quote_validity_days between 1 and 90);

alter table public.organization_settings drop constraint if exists organization_settings_identity_length_check;
alter table public.organization_settings add constraint organization_settings_identity_length_check check (
    length(store_name) <= 120 and length(store_document) <= 30 and length(store_phone) <= 30
    and length(store_whatsapp) <= 30 and length(store_email) <= 160 and length(store_address) <= 240
    and length(store_website) <= 160 and length(document_terms) <= 2000
);

comment on column public.organization_settings.document_terms is
'Condições impressas na ordem de serviço/orçamento. Vazio = texto padrão do aplicativo.';
