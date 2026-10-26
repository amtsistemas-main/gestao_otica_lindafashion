# WhatsApp Business Cloud API — configuração

A função `process-customer-whatsapp-outbox` processa notificações de status de pedido a partir de `customer_notification_outbox`. O token da Meta é lido exclusivamente como segredo da Edge Function; nunca deve ser colocado no aplicativo desktop, no repositório ou em tabelas acessíveis ao cliente.

## 1. Criar ativos na Meta

1. Acesse [Meta for Developers](https://developers.facebook.com/) e crie/seleciona um aplicativo com o produto WhatsApp.
2. Configure uma WhatsApp Business Account (WABA) e registre/verifique o número remetente.
3. Gere um token de usuário do sistema com a permissão `whatsapp_business_messaging` e acesso ao ativo WhatsApp correspondente.
4. Copie o **Phone Number ID** (não é o número de telefone visível).
5. No WhatsApp Manager, crie e obtenha aprovação de um modelo de mensagem da categoria Utility, com o corpo contendo apenas a variável `{{1}}`, por exemplo: `{{1}}`. Use o nome e idioma exatos do modelo aprovado.

Mensagens iniciadas pela empresa exigem modelo aprovado; o texto personalizado da aplicação será enviado como valor do parâmetro `{{1}}`. A aprovação do modelo é responsabilidade da Meta.

## 2. Cadastrar segredos da Edge Function

No painel do projeto Supabase `swlccwcykxmvwptzxrxt`, abra Edge Functions / Secrets e adicione:

- `WHATSAPP_ACCESS_TOKEN`: token de acesso da Meta.
- `WHATSAPP_PHONE_NUMBER_ID`: ID do número remetente.
- `WHATSAPP_TEMPLATE_NAME`: nome exato do modelo Utility aprovado.
- `WHATSAPP_TEMPLATE_LANGUAGE`: código de idioma aprovado, normalmente `pt_BR`.
- `WHATSAPP_GRAPH_API_VERSION`: versão da Graph API habilitada para o aplicativo Meta.

Não cadastrar o token no desktop, no GitHub, no SQL ou na interface do sistema. A função usa também `SUPABASE_URL` e `SUPABASE_SERVICE_ROLE_KEY` do ambiente de Edge Functions.

## 3. Execução e agendamento

A Edge Function foi implantada com verificação JWT ativada. URL:

`https://swlccwcykxmvwptzxrxt.supabase.co/functions/v1/process-customer-whatsapp-outbox`

O worker processa lotes de até 10 itens por execução. Para automação contínua, configure Supabase Cron (por exemplo, a cada minuto) para fazer POST para essa URL com `Authorization: Bearer <SUPABASE_SERVICE_ROLE_KEY>` e `Content-Type: application/json`. Guarde a chave em Supabase Vault/segredo de cron, nunca no SQL versionado nem no aplicativo. Não agende antes de cadastrar os segredos e testar um destinatário autorizado.

## 4. Retentativas e idempotência

- A fila marca itens como `processing` antes do envio e usa `FOR UPDATE SKIP LOCKED` para impedir dois workers de reivindicarem simultaneamente o mesmo item.
- Erros temporários (HTTP 408, 425, 429 e 5xx) são reagendados com backoff exponencial; limite de seis tentativas.
- Erros permanentes e números inválidos são registrados como `failed`.
- O ID da mensagem retornado pela Meta é guardado em `provider_message_id`.
- Se a Meta aceitar uma mensagem mas a confirmação no banco falhar, o item fica para reconciliação manual em vez de reenviar automaticamente.

A API da Meta não oferece uma chave de idempotência geral para este endpoint de envio. Em falhas de rede ambíguas, não é possível garantir entrega externa exatamente uma vez; esses casos devem ser reconciliados pelo status do provedor.

## 5. Teste controlado

1. Use um destinatário de teste que autorizou contato.
2. Confirme WhatsApp em formato internacional e `whatsapp_consent=true`.
3. Ative o modelo de status no módulo Clientes.
4. Crie/atualize um pedido e confirme uma linha `pending` na fila.
5. Execute o worker manualmente com JWT de serviço e confirme `sent`, `provider_message_id` e recebimento no telefone de teste.
6. Teste erro temporário e confirme que `next_attempt_at` agenda nova tentativa.

**Estado atual:** função implantada, fila preparada para retentativas e documentação adicionada. O envio real ainda depende das credenciais Meta, da aprovação do template e do agendamento.
