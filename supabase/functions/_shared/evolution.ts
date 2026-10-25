// Evolution API v2 client (gateway hosted by AMT, one instance per organization).
// Endpoints follow https://doc.evolution-api.com (v2). URL and global key are Edge Function
// secrets: EVOLUTION_API_URL and EVOLUTION_API_KEY — they never reach the desktop app.
import { HttpError } from "./http.ts";

export type ConnectionState = "open" | "connecting" | "close" | "unknown";

export class EvolutionError extends Error {
  constructor(public status: number, message: string, public retryable: boolean) {
    super(message);
  }
}

export function evolutionConfigured(): boolean {
  return Boolean(Deno.env.get("EVOLUTION_API_URL") && Deno.env.get("EVOLUTION_API_KEY"));
}

/** Instance name unique per Supabase project and organization (one AMT server, many stores). */
export function instanceNameFor(organizationId: string): string {
  const host = new URL(Deno.env.get("SUPABASE_URL") ?? "https://local.supabase.co").hostname;
  const project = host.split(".")[0].slice(0, 20);
  return `lf-${project}-${organizationId.replaceAll("-", "")}`;
}

async function call(path: string, init: RequestInit = {}, timeoutMs = 20000): Promise<any> {
  const base = (Deno.env.get("EVOLUTION_API_URL") ?? "").replace(/\/+$/, "");
  const key = Deno.env.get("EVOLUTION_API_KEY") ?? "";
  if (!base || !key) {
    throw new HttpError(503, "O gateway de WhatsApp ainda não foi configurado no servidor. Fale com a AMT Sistemas.");
  }
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  let response: Response;
  try {
    response = await fetch(`${base}${path}`, {
      ...init,
      signal: controller.signal,
      headers: { "content-type": "application/json", apikey: key, ...(init.headers ?? {}) },
    });
  } catch (_error) {
    throw new EvolutionError(0, "Gateway de WhatsApp indisponível no momento.", true);
  } finally {
    clearTimeout(timer);
  }
  const text = await response.text();
  let payload: any = null;
  try {
    payload = text ? JSON.parse(text) : null;
  } catch {
    payload = { raw: text.slice(0, 300) };
  }
  if (!response.ok) {
    const detail = JSON.stringify(payload ?? {}).slice(0, 400);
    if (/"exists"\s*:\s*false/.test(detail)) {
      throw new EvolutionError(response.status, "Este número não possui WhatsApp.", false);
    }
    const retryable = response.status === 408 || response.status === 429 || response.status >= 500;
    throw new EvolutionError(response.status, `Gateway respondeu ${response.status}: ${detail}`, retryable);
  }
  return payload;
}

export async function createInstance(name: string, webhookUrl: string): Promise<any> {
  return await call("/instance/create", {
    method: "POST",
    body: JSON.stringify({
      instanceName: name,
      qrcode: true,
      integration: "WHATSAPP-BAILEYS",
      webhook: {
        url: webhookUrl,
        byEvents: false,
        base64: false,
        events: ["CONNECTION_UPDATE", "QRCODE_UPDATED"],
      },
    }),
  });
}

export async function instanceExists(name: string): Promise<boolean> {
  try {
    const data = await call(`/instance/fetchInstances?instanceName=${encodeURIComponent(name)}`, { method: "GET" });
    return Array.isArray(data) ? data.length > 0 : Boolean(data);
  } catch (error) {
    if (error instanceof EvolutionError && (error.status === 404 || error.status === 400)) return false;
    throw error;
  }
}

/** QR code (data URL in `base64`) and pairing code for linking the phone. */
export async function connectQr(name: string): Promise<{ base64: string; pairingCode: string; code: string }> {
  const data = await call(`/instance/connect/${encodeURIComponent(name)}`, { method: "GET" });
  const qr = data?.qrcode ?? data ?? {};
  return { base64: String(qr.base64 ?? ""), pairingCode: String(qr.pairingCode ?? ""), code: String(qr.code ?? "") };
}

export async function connectionState(name: string): Promise<ConnectionState> {
  try {
    const data = await call(`/instance/connectionState/${encodeURIComponent(name)}`, { method: "GET" }, 10000);
    const state = String(data?.instance?.state ?? data?.state ?? "unknown");
    return (["open", "connecting", "close"].includes(state) ? state : "unknown") as ConnectionState;
  } catch (error) {
    if (error instanceof EvolutionError && error.status === 404) return "close";
    throw error;
  }
}

/** Phone number and profile name of the linked WhatsApp. */
export async function instanceProfile(name: string): Promise<{ phone: string; profile: string }> {
  try {
    const data = await call(`/instance/fetchInstances?instanceName=${encodeURIComponent(name)}`, { method: "GET" }, 10000);
    const item = Array.isArray(data) ? data[0] : data;
    const info = item?.instance ?? item ?? {};
    const jid = String(info.ownerJid ?? info.owner ?? "");
    return { phone: jid.split("@")[0].replace(/\D/g, ""), profile: String(info.profileName ?? "") };
  } catch {
    return { phone: "", profile: "" };
  }
}

export async function logout(name: string): Promise<void> {
  try {
    await call(`/instance/logout/${encodeURIComponent(name)}`, { method: "DELETE" });
  } catch (error) {
    if (!(error instanceof EvolutionError && [400, 404].includes(error.status))) throw error;
  }
}

export async function deleteInstance(name: string): Promise<void> {
  try {
    await call(`/instance/delete/${encodeURIComponent(name)}`, { method: "DELETE" });
  } catch (error) {
    if (!(error instanceof EvolutionError && [400, 404].includes(error.status))) throw error;
  }
}

function messageId(data: any): string {
  return String(data?.key?.id ?? data?.messageId ?? data?.id ?? "");
}

export async function sendText(name: string, number: string, text: string): Promise<string> {
  const data = await call(`/message/sendText/${encodeURIComponent(name)}`, {
    method: "POST",
    // `delay` shows "typing…" before sending, closer to a human pace.
    body: JSON.stringify({ number, text, delay: 1200 }),
  }, 30000);
  return messageId(data);
}

export async function sendDocument(name: string, number: string, mediaUrl: string, fileName: string, caption: string): Promise<string> {
  const data = await call(`/message/sendMedia/${encodeURIComponent(name)}`, {
    method: "POST",
    body: JSON.stringify({
      number,
      mediatype: "document",
      mimetype: "application/pdf",
      media: mediaUrl,
      fileName,
      caption,
      delay: 1200,
    }),
  }, 60000);
  return messageId(data);
}
