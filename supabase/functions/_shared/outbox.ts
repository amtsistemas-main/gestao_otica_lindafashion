// Outbox delivery shared by the scheduled worker and the app's "send now" calls.
// Each row is sent through the organization's provider: the Evolution instance when the
// store's WhatsApp is connected, or the Meta Cloud API when those secrets are configured.
import type { SupabaseClient } from "npm:@supabase/supabase-js@2";
import * as evolution from "./evolution.ts";

export type OutboxRow = {
  id: string;
  organization_id: string;
  recipient: string;
  message_body: string;
  attachment_path: string | null;
  attachment_name: string | null;
  attempts: number;
};

export type DeliveryResult = { id: string; status: "sent" | "retry" | "failed"; error?: string };

const DOCUMENTS_BUCKET = "whatsapp-documents";
const DAILY_LIMIT = 500;           // per store: protects the number from being flagged as spam
const PAUSE_BETWEEN_MESSAGES = 1500; // ms between sends of the same instance
const NOT_CONNECTED_DELAY = 1800;  // s: store's WhatsApp disconnected

export function retryDelay(attempt: number): number {
  return Math.min(21600, 60 * 2 ** Math.max(0, attempt - 1));
}

function metaConfigured(): boolean {
  return Boolean(Deno.env.get("WHATSAPP_ACCESS_TOKEN") && Deno.env.get("WHATSAPP_PHONE_NUMBER_ID")
    && Deno.env.get("WHATSAPP_TEMPLATE_NAME") && Deno.env.get("WHATSAPP_GRAPH_API_VERSION"));
}

async function fail(admin: SupabaseClient, row: OutboxRow, error: string, retry: boolean, delay: number): Promise<DeliveryResult> {
  await admin.rpc("fail_customer_whatsapp_outbox", {
    p_id: row.id, p_error: error.slice(0, 1000), p_retry: retry, p_delay_seconds: delay,
  });
  return { id: row.id, status: retry && row.attempts < 6 ? "retry" : "failed", error };
}

async function complete(admin: SupabaseClient, row: OutboxRow, provider: string, messageId: string): Promise<DeliveryResult> {
  await admin.from("customer_notification_outbox").update({ provider }).eq("id", row.id);
  const { error } = await admin.rpc("complete_customer_whatsapp_outbox", {
    p_id: row.id, p_provider_message_id: messageId || `${provider}-${row.id}`,
  });
  if (error) {
    // The provider accepted it: never resend blindly (duplicate delivery to the customer).
    return await fail(admin, row, "Mensagem aceita pelo provedor, mas não confirmada no banco. Verifique antes de reenviar.", false, 60);
  }
  return { id: row.id, status: "sent" };
}

async function sendViaMeta(row: OutboxRow, phone: string): Promise<string> {
  const version = Deno.env.get("WHATSAPP_GRAPH_API_VERSION");
  const phoneId = Deno.env.get("WHATSAPP_PHONE_NUMBER_ID");
  const response = await fetch(`https://graph.facebook.com/${version}/${phoneId}/messages`, {
    method: "POST",
    headers: { authorization: `Bearer ${Deno.env.get("WHATSAPP_ACCESS_TOKEN")}`, "content-type": "application/json" },
    body: JSON.stringify({
      messaging_product: "whatsapp",
      recipient_type: "individual",
      to: phone,
      type: "template",
      template: {
        name: Deno.env.get("WHATSAPP_TEMPLATE_NAME"),
        language: { code: Deno.env.get("WHATSAPP_TEMPLATE_LANGUAGE") ?? "pt_BR" },
        components: [{ type: "body", parameters: [{ type: "text", text: row.message_body.slice(0, 1024) }] }],
      },
    }),
    signal: AbortSignal.timeout(15000),
  });
  const payload = await response.json().catch(() => ({}));
  const id = payload?.messages?.[0]?.id as string | undefined;
  if (response.ok && id) return id;
  const retryable = response.status === 408 || response.status === 425 || response.status === 429 || response.status >= 500;
  const message = typeof payload?.error?.message === "string" ? payload.error.message.slice(0, 400) : `HTTP ${response.status}`;
  throw new evolution.EvolutionError(response.status, `Meta API ${response.status}: ${message}`, retryable);
}

type OrgChannel = { kind: "evolution"; instance: string } | { kind: "meta" } | { kind: "none"; reason: string };

async function channelFor(admin: SupabaseClient, organizationId: string, cache: Map<string, OrgChannel>): Promise<OrgChannel> {
  const cached = cache.get(organizationId);
  if (cached) return cached;
  let channel: OrgChannel = { kind: "none", reason: "O WhatsApp da loja não está conectado." };
  const { data } = await admin.from("whatsapp_connections")
    .select("instance_name, status, provider").eq("organization_id", organizationId).maybeSingle();
  if (data?.provider === "evolution" && data.instance_name && evolution.evolutionConfigured()) {
    channel = data.status === "connected"
      ? { kind: "evolution", instance: data.instance_name }
      : { kind: "none", reason: "O WhatsApp da loja está desconectado. Conecte novamente em Configurações." };
  } else if (metaConfigured()) {
    channel = { kind: "meta" };
  }
  cache.set(organizationId, channel);
  return channel;
}

async function sentToday(admin: SupabaseClient, organizationId: string): Promise<number> {
  const since = new Date();
  since.setUTCHours(0, 0, 0, 0);
  const { count } = await admin.from("customer_notification_outbox")
    .select("id", { count: "exact", head: true })
    .eq("organization_id", organizationId).eq("channel", "whatsapp").eq("status", "sent")
    .gte("sent_at", since.toISOString());
  return count ?? 0;
}

export async function deliver(admin: SupabaseClient, rows: OutboxRow[]): Promise<DeliveryResult[]> {
  const results: DeliveryResult[] = [];
  const channels = new Map<string, OrgChannel>();
  const lastSend = new Map<string, number>();

  for (const row of rows) {
    try {
      const phone = String(row.recipient ?? "").replace(/\D/g, "");
      if (!/^\d{12,15}$/.test(phone)) {
        results.push(await fail(admin, row, "Número de WhatsApp inválido; informe DDD e número.", false, 60));
        continue;
      }
      const channel = await channelFor(admin, row.organization_id, channels);
      if (channel.kind === "none") {
        results.push(await fail(admin, row, channel.reason, true, NOT_CONNECTED_DELAY));
        continue;
      }
      if (await sentToday(admin, row.organization_id) >= DAILY_LIMIT) {
        results.push(await fail(admin, row, "Limite diário de mensagens da loja atingido; envio adiado.", true, 3600));
        continue;
      }

      if (channel.kind === "meta") {
        if (row.attachment_path) {
          results.push(await fail(admin, row, "O envio de documentos exige o WhatsApp conectado por QR Code.", false, 60));
          continue;
        }
        results.push(await complete(admin, row, "meta_cloud", await sendViaMeta(row, phone)));
        continue;
      }

      // Pace messages per instance (spam protection).
      const previous = lastSend.get(channel.instance) ?? 0;
      const wait = PAUSE_BETWEEN_MESSAGES - (Date.now() - previous);
      if (wait > 0) await new Promise((resolve) => setTimeout(resolve, wait));

      let messageId: string;
      if (row.attachment_path) {
        const { data: signed, error } = await admin.storage.from(DOCUMENTS_BUCKET)
          .createSignedUrl(row.attachment_path, 900);
        if (error || !signed?.signedUrl) {
          results.push(await fail(admin, row, "Documento não encontrado para envio.", false, 60));
          continue;
        }
        messageId = await evolution.sendDocument(channel.instance, phone, signed.signedUrl,
          row.attachment_name || "documento.pdf", row.message_body);
      } else {
        messageId = await evolution.sendText(channel.instance, phone, row.message_body);
      }
      lastSend.set(channel.instance, Date.now());
      results.push(await complete(admin, row, "evolution", messageId));
    } catch (error) {
      if (error instanceof evolution.EvolutionError) {
        results.push(await fail(admin, row, error.message, error.retryable, retryDelay(row.attempts)));
      } else {
        const message = error instanceof Error ? error.message : "Falha desconhecida";
        results.push(await fail(admin, row, `Falha de transporte: ${message.slice(0, 300)}`, true, retryDelay(row.attempts)));
      }
    }
  }
  return results;
}
