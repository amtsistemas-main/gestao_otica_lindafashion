import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "npm:@supabase/supabase-js@2";

type OutboxRow = {
  id: string;
  organization_id: string;
  customer_id: string;
  order_id: string | null;
  event_type: string;
  recipient: string;
  message_body: string;
  attempts: number;
};

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", "cache-control": "no-store" },
  });

function retryDelay(attempt: number): number {
  return Math.min(21600, 60 * 2 ** Math.max(0, attempt - 1));
}

function isRetryable(status: number): boolean {
  return status === 408 || status === 425 || status === 429 || status >= 500;
}

Deno.serve(async (req: Request) => {
  if (req.method !== "POST") return json({ error: "method_not_allowed" }, 405);

  const url = Deno.env.get("SUPABASE_URL");
  const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  const accessToken = Deno.env.get("WHATSAPP_ACCESS_TOKEN");
  const phoneNumberId = Deno.env.get("WHATSAPP_PHONE_NUMBER_ID");
  const templateName = Deno.env.get("WHATSAPP_TEMPLATE_NAME");
  const language = Deno.env.get("WHATSAPP_TEMPLATE_LANGUAGE") ?? "pt_BR";
  const graphVersion = Deno.env.get("WHATSAPP_GRAPH_API_VERSION");

  if (!url || !serviceKey) return json({ error: "server_configuration_incomplete" }, 500);
  if (!accessToken || !phoneNumberId || !templateName || !graphVersion) {
    return json({
      error: "whatsapp_provider_not_configured",
      required_secrets: [
        "WHATSAPP_ACCESS_TOKEN",
        "WHATSAPP_PHONE_NUMBER_ID",
        "WHATSAPP_TEMPLATE_NAME",
        "WHATSAPP_GRAPH_API_VERSION",
      ],
    }, 503);
  }

  const supabase = createClient(url, serviceKey, {
    auth: { persistSession: false, autoRefreshToken: false },
  });

  const { data: claimed, error: claimError } = await supabase.rpc(
    "claim_customer_whatsapp_outbox",
    { p_batch_size: 10 },
  );
  if (claimError) {
    console.error("outbox_claim_failed", claimError.code ?? "unknown");
    return json({ error: "outbox_claim_failed" }, 500);
  }

  const rows = (claimed ?? []) as OutboxRow[];
  let sent = 0;
  let failed = 0;
  let retried = 0;

  for (const row of rows) {
    try {
      const phone = String(row.recipient ?? "").replace(/\D/g, "");
      if (!/^\d{10,15}$/.test(phone)) {
        await supabase.rpc("fail_customer_whatsapp_outbox", {
          p_id: row.id,
          p_error: "Número de WhatsApp inválido; use DDI + DDD + número.",
          p_retry: false,
          p_delay_seconds: 60,
        });
        failed++;
        continue;
      }

      // The full personalized text is passed as the single {{1}} parameter of a
      // Meta-approved Utility template. Meta approval is required before sending.
      const response = await fetch(
        `https://graph.facebook.com/${graphVersion}/${phoneNumberId}/messages`,
        {
          method: "POST",
          headers: {
            "authorization": `Bearer ${accessToken}`,
            "content-type": "application/json",
          },
          body: JSON.stringify({
            messaging_product: "whatsapp",
            recipient_type: "individual",
            to: phone,
            type: "template",
            template: {
              name: templateName,
              language: { code: language },
              components: [{
                type: "body",
                parameters: [{ type: "text", text: row.message_body.slice(0, 1024) }],
              }],
            },
          }),
          signal: AbortSignal.timeout(15000),
        },
      );

      const payload = await response.json().catch(() => ({}));
      const messageId = payload?.messages?.[0]?.id as string | undefined;
      if (response.ok && messageId) {
        const { error } = await supabase.rpc("complete_customer_whatsapp_outbox", {
          p_id: row.id,
          p_provider_message_id: messageId,
        });
        if (error) {
          // Do not resend blindly: Meta accepted the message. Keep the row failed
          // for manual reconciliation rather than risk a duplicate delivery.
          await supabase.rpc("fail_customer_whatsapp_outbox", {
            p_id: row.id,
            p_error: "Meta aceitou a mensagem, mas não foi possível confirmar no banco. Verificar o ID do provedor antes de reprocessar.",
            p_retry: false,
            p_delay_seconds: 60,
          });
          failed++;
        } else {
          sent++;
        }
        continue;
      }

      const providerCode = payload?.error?.code;
      const providerMessage = typeof payload?.error?.message === "string"
        ? payload.error.message.slice(0, 500)
        : `HTTP ${response.status} retornado pela API WhatsApp.`;
      const retryable = isRetryable(response.status);
      const delay = retryDelay(row.attempts);
      await supabase.rpc("fail_customer_whatsapp_outbox", {
        p_id: row.id,
        p_error: `Meta API ${response.status}${providerCode ? ` (código ${providerCode})` : ""}: ${providerMessage}`,
        p_retry: retryable,
        p_delay_seconds: delay,
      });
      if (retryable && row.attempts < 6) retried++;
      else failed++;
    } catch (error) {
      const message = error instanceof Error ? error.message : "Falha de rede desconhecida";
      await supabase.rpc("fail_customer_whatsapp_outbox", {
        p_id: row.id,
        p_error: `Falha de transporte: ${message.slice(0, 500)}`,
        p_retry: true,
        p_delay_seconds: retryDelay(row.attempts),
      });
      if (row.attempts < 6) retried++;
      else failed++;
    }
  }

  return json({ claimed: rows.length, sent, retried, failed });
});
