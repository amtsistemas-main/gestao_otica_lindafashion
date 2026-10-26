import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { adminClient, json, safeEqual } from "../_shared/http.ts";
import * as evolution from "../_shared/evolution.ts";

// Events from the Evolution gateway (connection opened/closed). Public endpoint without JWT:
// it is authenticated by the per-store secret in the URL, created by whatsapp-connect.
// Always answers 200 for valid calls so the gateway does not retry endlessly.

Deno.serve(async (req: Request) => {
  if (req.method !== "POST") return json({ error: "Método não permitido." }, 405);
  try {
    const url = new URL(req.url);
    const org = url.searchParams.get("org") ?? "";
    const secret = url.searchParams.get("secret") ?? "";
    if (!org || !secret) return json({ error: "Não autorizado." }, 401);
    const admin = adminClient();
    const { data: stored } = await admin.from("whatsapp_instance_secrets")
      .select("webhook_secret").eq("organization_id", org).maybeSingle();
    if (!stored?.webhook_secret || !safeEqual(stored.webhook_secret, secret)) return json({ error: "Não autorizado." }, 401);

    const payload = await req.json().catch(() => ({})) as Record<string, any>;
    const event = String(payload.event ?? "").toLowerCase().replace("_", ".");
    if (event !== "connection.update") return json({ ok: true });

    const state = String(payload.data?.state ?? "");
    const now = new Date().toISOString();
    const instance = evolution.instanceNameFor(org);
    if (state === "open") {
      const profile = await evolution.instanceProfile(instance);
      await admin.from("whatsapp_connections").update({
        status: "connected", phone_number: profile.phone, profile_name: profile.profile,
        connected_at: now, last_error: "", updated_at: now,
      }).eq("organization_id", org);
    } else if (state === "close") {
      await admin.from("whatsapp_connections").update({
        status: "disconnected", last_error: "O WhatsApp foi desconectado no celular.", updated_at: now,
      }).eq("organization_id", org).eq("status", "connected");
    } else if (state === "connecting") {
      await admin.from("whatsapp_connections").update({ status: "connecting", updated_at: now })
        .eq("organization_id", org).neq("status", "connected");
    }
    return json({ ok: true });
  } catch (_error) {
    console.error("whatsapp-webhook: erro inesperado");
    return json({ ok: false }, 200);
  }
});
