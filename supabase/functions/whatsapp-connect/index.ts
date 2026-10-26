import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { adminClient, callerMember, handleError, HttpError, json } from "../_shared/http.ts";
import * as evolution from "../_shared/evolution.ts";

// Store WhatsApp connection by QR Code (Evolution instance per organization).
// Actions:
//   status      (any member)        -> current connection; refreshes it from the gateway
//   connect     (owner/admin)       -> creates the instance if needed and returns the QR Code
//   disconnect  (owner/admin)       -> unlinks the phone and removes the instance
//   test        (owner/admin)       -> sends a test message to `number`

type Connection = {
  organization_id: string;
  instance_name: string;
  status: string;
  phone_number: string;
  profile_name: string;
  connected_at: string | null;
  last_error: string;
};

function publicView(row: Partial<Connection> | null) {
  return {
    configured: evolution.evolutionConfigured(),
    status: row?.status ?? "disconnected",
    phone_number: row?.phone_number ?? "",
    profile_name: row?.profile_name ?? "",
    connected_at: row?.connected_at ?? null,
    last_error: row?.last_error ?? "",
  };
}

function randomSecret(): string {
  const bytes = new Uint8Array(24);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
}

Deno.serve(async (req: Request) => {
  if (req.method !== "POST") return json({ error: "Método não permitido." }, 405);
  try {
    const body = await req.json().catch(() => null) as Record<string, unknown> | null;
    if (!body) throw new HttpError(400, "Requisição inválida.");
    const action = String(body.action ?? "");
    const org = String(body.organization_id ?? "");
    const admin = adminClient();
    const member = await callerMember(admin, req, org);
    const manager = ["owner", "admin"].includes(member.role);

    const { data: current } = await admin.from("whatsapp_connections").select("*").eq("organization_id", org).maybeSingle();
    const save = async (changes: Partial<Connection>) => {
      const row = { organization_id: org, instance_name: evolution.instanceNameFor(org), ...changes,
        updated_at: new Date().toISOString() };
      const { data, error } = await admin.from("whatsapp_connections").upsert(row).select("*").single();
      if (error) throw new HttpError(500, "Não foi possível salvar a conexão do WhatsApp.");
      return data as Connection;
    };

    if (action === "status") {
      if (!current || !evolution.evolutionConfigured()) return json(publicView(current));
      const state = await evolution.connectionState(current.instance_name).catch(() => "unknown" as const);
      if (state === "unknown") return json(publicView(current));
      let changes: Partial<Connection> = {};
      if (state === "open" && current.status !== "connected") {
        const profile = await evolution.instanceProfile(current.instance_name);
        changes = { status: "connected", phone_number: profile.phone, profile_name: profile.profile,
          connected_at: new Date().toISOString(), last_error: "" };
      } else if (state === "close" && current.status === "connected") {
        changes = { status: "disconnected", last_error: "O WhatsApp foi desconectado no celular." };
      } else if (state === "connecting" && current.status === "disconnected") {
        changes = { status: "connecting" };
      }
      return json(publicView(Object.keys(changes).length ? await save(changes) : current));
    }

    if (!manager) throw new HttpError(403, "Somente donos e administradores gerenciam o WhatsApp da loja.");

    if (action === "connect") {
      const name = evolution.instanceNameFor(org);
      let secret: string;
      const { data: stored } = await admin.from("whatsapp_instance_secrets").select("webhook_secret").eq("organization_id", org).maybeSingle();
      if (stored?.webhook_secret) {
        secret = stored.webhook_secret;
      } else {
        secret = randomSecret();
        await admin.from("whatsapp_instance_secrets").upsert({ organization_id: org, webhook_secret: secret });
      }
      const webhook = `${Deno.env.get("SUPABASE_URL")}/functions/v1/whatsapp-webhook?org=${org}&secret=${secret}`;
      let qr = { base64: "", pairingCode: "", code: "" };
      if (!(await evolution.instanceExists(name))) {
        const created = await evolution.createInstance(name, webhook);
        const fromCreate = created?.qrcode ?? {};
        qr = { base64: String(fromCreate.base64 ?? ""), pairingCode: String(fromCreate.pairingCode ?? ""), code: String(fromCreate.code ?? "") };
      }
      const state = await evolution.connectionState(name).catch(() => "unknown" as const);
      if (state === "open") {
        const profile = await evolution.instanceProfile(name);
        const row = await save({ status: "connected", phone_number: profile.phone, profile_name: profile.profile,
          connected_at: new Date().toISOString(), last_error: "" });
        return json({ ...publicView(row), qr_base64: "", pairing_code: "" });
      }
      if (!qr.base64) qr = await evolution.connectQr(name);
      const row = await save({ status: "connecting", last_error: "" });
      return json({ ...publicView(row), qr_base64: qr.base64, pairing_code: qr.pairingCode });
    }

    if (action === "disconnect") {
      if (current?.instance_name) {
        await evolution.logout(current.instance_name);
        await evolution.deleteInstance(current.instance_name);
      }
      const row = await save({ status: "disconnected", phone_number: "", profile_name: "", connected_at: null, last_error: "" });
      return json(publicView(row));
    }

    if (action === "test") {
      if (current?.status !== "connected") throw new HttpError(409, "Conecte o WhatsApp da loja antes de enviar o teste.");
      const digits = String(body.number ?? "").replace(/\D/g, "").replace(/^0+/, "");
      const number = digits.length === 10 || digits.length === 11 ? `55${digits}` : digits;
      if (!/^\d{12,15}$/.test(number)) throw new HttpError(400, "Informe o número com DDD.");
      try {
        await evolution.sendText(current.instance_name, number,
          "✅ Teste de envio: o WhatsApp da loja está conectado ao sistema de gestão.");
      } catch (error) {
        if (error instanceof evolution.EvolutionError) throw new HttpError(502, error.message);
        throw error;
      }
      return json({ ok: true });
    }

    throw new HttpError(400, "Ação desconhecida.");
  } catch (error) {
    if (error instanceof evolution.EvolutionError) return json({ error: error.message }, 502);
    return handleError("whatsapp-connect", error);
  }
});
