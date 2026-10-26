# Supabase migrations and local connection

The application is configured for the Ótica Linda Fashion Supabase project:
`https://swlccwcykxmvwptzxrxt.supabase.co`.

## Configure the desktop application

1. Copy `.env.example` to `.env` in the project root.
2. In the Supabase Dashboard for this project, open **Connect** or **Settings → API Keys** and copy the **publishable** key (usually starts with `sb_publishable_`). A legacy `anon` key is also a public client key if the project has not created publishable keys yet.
3. Paste that value into `SUPABASE_PUBLISHABLE_KEY` in your local `.env`.
4. Restart the application. Do not commit `.env` and never use a `service_role` or secret key in this desktop application.

The project URL is configured as a safe default in `config/settings.py`; it can still be overridden through `SUPABASE_URL`.

## Gestão óptica de alto padrão — aplicar nesta ordem

Pré-requisito: as migrations anteriores (`202610240001` a `202610241730`, nesta pasta e em `supabase/migrations/`) já aplicadas — em especial clientes/CRM (006), pedidos (007), eventos e fila (008), modelos de WhatsApp (010/011), fornecedores (005), financeiro (006) e vendas (241700).

| Ordem | Arquivo | O que faz |
|---|---|---|
| 1 | `202610250001_optical_products.sql` | Tipo de produto (armação, lente oftálmica, lente de contato, solar, acessório, serviço), modelo, cor, tamanho, material, atributos de lente, quantidade de reposição e itens sem controle de estoque. |
| 2 | `202610250002_customer_prescriptions.sql` | Receitas OD/OE estruturadas com validação no banco (passos de 0,25 D, eixo 0–180 obrigatório com cilindro, faixas de DNP/altura) e vínculo da venda com a receita e as medidas da armação. |
| 3 | `202610250003_lab_order_pipeline.sql` | Fluxo de 8 status do pedido (aguardando envio → entregue/cancelado), laboratório, custo, prazos, datas de cada etapa preenchidas pelo banco, ocorrências e fila de WhatsApp atualizada. Converte os status antigos sem disparar mensagens. |
| 4 | `202610250004_pos_payments_quotes.sql` | Configurações da loja (limite de desconto), nome de exibição da equipe, pagamentos múltiplos (sinal, crediário/boleto parcelado), orçamentos, chave de idempotência, `finalize_sales_order_v2` (venda transacional com baixa de estoque auditada, financeiro e pedido de laboratório) e `cancel_sales_order` (devolução ao estoque e estorno). |
| 5 | `202610250005_commercial_intelligence.sql` | Preenche o custo histórico dos itens já vendidos (aproximação pelo custo atual) e cria índices dos indicadores. |
| 6 | `202610250006_crm_repurchase.sql` | Preferências do cliente, agenda `crm_tasks` e tarefas automáticas de pós-venda (pedido entregue) e revisão de receita (antes do vencimento). |
| 7 | `202610250007_sales_write_through_rpc.sql` | Vendas, itens e pagamentos passam a ser somente leitura pela API; a gravação ocorre apenas por `finalize_sales_order_v2`/`cancel_sales_order` (security definer), impedindo contornar o limite de desconto, a conferência de pagamentos e a baixa de estoque. Revoga a função antiga `finalize_sales_order`. |
| 8 | `202610250008_trigger_functions_not_rpc.sql` | Remove a exposição das funções de gatilho como RPC (os gatilhos continuam funcionando). |
| 9 | `202610250009_store_document_identity.sql` | Dados da loja impressos nos documentos de venda (nome, CNPJ, contatos, endereço, validade do orçamento e condições). |
| 10 | `202610250010_multi_user_module_access.sql` | Multilogin: e-mail e módulos liberados por usuário (`allowed_modules`), função `has_module_access` e RLS do Financeiro por módulo (ler exige Financeiro ou Indicadores; gravar exige Financeiro). |
| 11 | `202610250011_whatsapp_gateway.sql` | WhatsApp por gateway (Evolution): conexão por loja (`whatsapp_connections`), segredos só no servidor, número no formato internacional (`normalize_br_whatsapp`), fila sem duplicidade e com recuperação de mensagens travadas, inserção apenas por `enqueue_whatsapp_message` e bucket privado `whatsapp-documents`. |
| 12 | `202610250012_whatsapp_worker_schedule.sql` | Envio validado pelo cadastro do cliente (limite por usuário) e worker agendado no `pg_cron` (chama a Edge Function só quando há mensagens; URL e segredo no Vault). |
| 13 | `202610250013_service_role_grants.sql` | Privilégios do `service_role` (somente servidor) nas tabelas, inclusive futuras. Sem eles as Edge Functions não liam os vínculos e respondiam "sem vínculo". |
| 14 | `202610250014_username_login.sql` | Login por nome de usuário: coluna `organization_members.username` (única), e-mail interno `<usuario>@usuarios.local` no Supabase Auth. |
| 15 | `202610250015_sales_order_status.sql` | Venda vinculada ao pedido: `finalize_sales_order_v2` recebe o status atual do pedido (`p_order_status`), modelos de mensagem para "aguardando envio" e "enviado ao laboratório" e variável `{{loja}}` nas mensagens de WhatsApp. |
| 16 | `202610260016_order_whatsapp_every_change.sql` | Corrige mensagens de status descartadas: a chave de deduplicação passa a ser por mudança de status (inclui a transação), então um pedido que volta a uma etapa já avisada gera nova mensagem. |
| 17 | `202610260017_sales_seller.sql` | Vendedor em cada venda (comissões): `finalize_sales_order_v2` recebe `p_seller_id`, validado como usuário ativo da organização; sem escolha, fica quem registra. |

As catorze migrations foram aplicadas no projeto conectado em 25/10/2026 e registradas em `supabase_migrations.schema_migrations`. O fluxo completo (venda com sinal e crediário, idempotência, pipeline do laboratório, pós-venda, orçamento, cancelamento com estorno, bloqueios por papel, RLS, acesso por módulo e fila do WhatsApp) foi validado como usuário autenticado, em transação revertida.

### Edge Function `admin-users` (multilogin)

Cria logins, edita perfil e módulos, redefine senha e ativa/desativa usuários. A chave de serviço existe só no servidor da função; o aplicativo envia apenas o token do usuário conectado, e a função confirma a cada chamada que ele é dono ou administrador ativo da organização (somente o dono cria administradores; ninguém altera o dono por ela). Publicada no projeto conectado. Para publicar em outro projeto:

```powershell
npx supabase functions deploy admin-users --project-ref <ref-do-projeto> --use-api
```

Para aplicar em outro projeto, execute cada arquivo no SQL Editor, na ordem, e confira a mensagem de sucesso antes do próximo. Depois disso, um dono/administrador deve abrir **Configurações** no aplicativo para definir o desconto máximo da loja (padrão 10%) e o nome de exibição de cada vendedor.

## Products — `202610240001_products.sql`

Before applying this migration, inspect the target project's actual schema and migration history to avoid conflicting with existing tables. Execute SQL migrations in this directory in order only after confirming they are needed.

The migration creates `organizations`, `organization_members` and `products`, indexes, an update trigger and organization-scoped RLS policies. The desktop client uses only a public/publishable key; database RLS is the authorization boundary.

### Provision the first organization

After confirming the migration is installed, create the organization in the SQL Editor and copy the returned UUID:

```sql
insert into public.organizations (name)
values ('Ótica Linda Fashion')
returning id;
```

Locate the UUID of the user created in Supabase Auth (Dashboard → Authentication → Users). Replace the two example values and execute:

```sql
insert into public.organization_members (organization_id, user_id, role, active)
values (
    'COLE_AQUI_O_UUID_DA_ORGANIZACAO'::uuid,
    'COLE_AQUI_O_UUID_DO_USUARIO_AUTH'::uuid,
    'owner',
    true
);
```

Perform this administrative provisioning in the Supabase Dashboard, never from the desktop app with a privileged key. The user needs an active organization membership to load and edit the product catalog.

The `python app.py --preview` mode uses temporary in-memory storage and never writes to Supabase. Preview data is discarded when the app closes.

### WhatsApp da loja (Evolution API)

Conexão por QR Code, fila, Edge Functions (`whatsapp-connect`, `whatsapp-send`, `process-customer-whatsapp-outbox`, `whatsapp-webhook`), servidor do gateway e segredos: veja `docs/whatsapp-evolution.md`.
