import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { adminClient, handleError, HttpError, json, safeEqual } from "../_shared/http.ts";
import { deliver, type OutboxRow } from "../_shared/outbox.ts";

// Scheduled worker (pg_cron, every minute): delivers pending WhatsApp messages of every
// store through its provider (Evolution instance or Meta Cloud API).
// Auth: the cron sends `x-cron-secret` (WHATSAPP_CRON_SECRET); the service role key in the
// Authorization header is also accepted for manual runs from the dashboard.

function authorized(req: Request): boolean {
  const cronSecret = Deno.env.get("WHATSAPP_CRON_SECRET") ?? "";
  const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
  const header = req.headers.get("x-cron-secret") ?? "";
  const bearer = (req.headers.get("Authorization") ?? "").replace(/^Bearer\s+/i, "").trim();
  return safeEqual(header, cronSecret) || safeEqual(bearer, serviceKey);
}

Deno.serve(async (req: Request) => {
  if (req.method !== "POST") return json({ error: "Método não permitido." }, 405);
  try {
    if (!authorized(req)) throw new HttpError(401, "Não autorizado.");
    const admin = adminClient();
    const { data, error } = await admin.rpc("claim_customer_whatsapp_outbox", { p_batch_size: 20 });
    if (error) throw new HttpError(500, "Não foi possível ler a fila de mensagens.");
    const results = await deliver(admin, (data ?? []) as OutboxRow[]);
    const count = (status: string) => results.filter((item) => item.status === status).length;
    return json({ claimed: results.length, sent: count("sent"), retried: count("retry"), failed: count("failed") });
  } catch (error) {
    return handleError("process-customer-whatsapp-outbox", error);
  }
});
