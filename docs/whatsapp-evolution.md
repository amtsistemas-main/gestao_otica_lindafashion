# WhatsApp da loja via Evolution API (QR Code)

O sistema envia WhatsApp por um **gateway Evolution API hospedado pela AMT**: um único servidor
atende todas as lojas, e cada loja ganha a sua própria instância, criada automaticamente.
O cliente final só abre **Configurações → WhatsApp da loja → Conectar WhatsApp** e escaneia o
QR Code com o celular da loja. Ele não informa URL, chave nem token.

Sem WhatsApp conectado, o sistema continua funcionando com o envio manual (abre o WhatsApp
no computador com a mensagem pronta e o PDF copiado).

## O que é enviado automaticamente

| Origem | Quando | Regras |
|---|---|---|
| Status do pedido (laboratório) | O pedido muda de etapa e há modelo de mensagem ativo | Cliente ativo, com consentimento de WhatsApp; no máximo uma mensagem por pedido e etapa |
| Documento da venda (PDF) | "Enviar pelo WhatsApp da loja" no visualizador de PDF | Confirmação no app; número do cadastro do cliente (ou digitado em venda avulsa) |
| Contato da venda | Botão WhatsApp na lista de vendas | Número do cadastro do cliente |
| Relacionamento (CRM) | Botão WhatsApp nas tarefas e segmentos | Consentimento obrigatório, verificado no banco |

Limites de proteção do número: no máximo 500 mensagens por loja por dia, pausa de 1,5 s entre
envios e indicação de "digitando…". Não existe envio em massa.

## Arquitetura

- **Fila** `customer_notification_outbox`: toda mensagem passa por ela (auditoria, novas tentativas,
  deduplicação). O app só insere pela função `enqueue_whatsapp_message`, que valida vínculo,
  módulo liberado, consentimento e usa o número do cadastro do cliente.
- **Edge Functions**:
  - `whatsapp-connect` — status, QR Code, desconexão e teste (dono/administrador);
  - `whatsapp-send` — envio imediato de uma mensagem recém-enfileirada (botões do app);
  - `process-customer-whatsapp-outbox` — worker chamado pelo `pg_cron` a cada minuto, somente
    quando há mensagens vencidas (autenticado por `x-cron-secret`);
  - `whatsapp-webhook` — eventos de conexão do gateway (autenticado por segredo por loja).
- **Provedores**: Evolution (QR Code) e, como alternativa, a API oficial da Meta
  (`docs/whatsapp-cloud-api-setup.md`) atrás da mesma fila.
- **Documentos**: bucket privado `whatsapp-documents` (pasta = organização); o gateway recebe um
  link assinado válido por 15 minutos.
- **Segredos**: `EVOLUTION_API_URL`, `EVOLUTION_API_KEY` e `WHATSAPP_CRON_SECRET` existem só nas
  Edge Functions; o segredo do cron também fica no Vault. Nada disso vai para o app desktop.

## Publicar o servidor (AMT, uma única vez)

1. VPS com Docker (2 vCPU, 4 GB de RAM atendem dezenas de lojas) e um domínio apontando para ele.
2. Copie `docs/evolution/` para o servidor, crie o `.env` a partir de `.env.example` e rode:
   ```bash
   docker compose up -d
   curl https://wa.seudominio.com.br/   # deve responder com a versão do Evolution
   ```
3. Configure os secrets no projeto Supabase de cada cliente (white label):
   ```powershell
   npx supabase secrets set EVOLUTION_API_URL=https://wa.seudominio.com.br EVOLUTION_API_KEY=<chave> --project-ref <ref>
   ```
   Os nomes das instâncias levam o identificador do projeto Supabase, então vários projetos podem
   usar o mesmo servidor sem conflito.
4. Faça backup diário do Postgres do gateway e monitore `GET /` (ex.: Uptime Kuma). Se as sessões
   forem perdidas, cada loja precisa escanear o QR Code de novo.

## Em outro projeto Supabase

Aplique as migrations `202610250011` e `202610250012`, publique as funções e crie os segredos:

```powershell
npx supabase functions deploy whatsapp-connect --project-ref <ref> --use-api
npx supabase functions deploy whatsapp-send --project-ref <ref> --use-api
npx supabase functions deploy process-customer-whatsapp-outbox --project-ref <ref> --use-api --no-verify-jwt
npx supabase functions deploy whatsapp-webhook --project-ref <ref> --use-api --no-verify-jwt
npx supabase secrets set WHATSAPP_CRON_SECRET=<valor aleatório> --project-ref <ref>
```

No SQL Editor (fora do SQL versionado):

```sql
select vault.create_secret('https://<ref>.supabase.co/functions/v1/process-customer-whatsapp-outbox', 'whatsapp_worker_url');
select vault.create_secret('<mesmo valor de WHATSAPP_CRON_SECRET>', 'whatsapp_cron_secret');
```

## Riscos

A conexão por QR Code não é a API oficial do WhatsApp. Uso abusivo (spam, listas compradas,
mensagens não solicitadas) pode levar ao bloqueio do número. O app exibe esse aviso e exige o
aceite antes de conectar. Para volume alto ou campanhas, use o canal oficial (a mesma fila e o
mesmo gateway suportam a integração `WHATSAPP-BUSINESS` do Evolution).
