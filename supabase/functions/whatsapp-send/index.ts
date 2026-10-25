import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { adminClient, callerMember, handleError, HttpError, json } from "../_shared/http.ts";
import { deliver, type OutboxRow } from "../_shared/outbox.ts";

// Immediate delivery of a message the app just queued (enqueue_whatsapp_message), so the
// user sees the result right away. Only messages of the caller's organization are sent.
// Body: { organization_id, outbox_id }

Deno.serve(async (req: Request) => {
  if (req.method !== "POST") return json({ error: "Método não permitido." }, 405);
  try {
    const body = await req.json().catch(() => null) as Record<string, unknown> | null;
    if (!body) throw new HttpError(400, "Requisição inválida.");
    const org = String(body.organization_id ?? "");
    const outboxId = String(body.outbox_id ?? "");
    const admin = adminClient();
    await callerMember(admin, req, org);
    if (!outboxId) throw new HttpError(400, "Mensagem não informada.");

    const { data: row } = await admin.from("customer_notification_outbox")
      .select("id, organization_id, status, provider_message_id, last_error")
      .eq("id", outboxId).eq("organization_id", org).maybeSingle();
    if (!row) throw new HttpError(404, "Mensagem não encontrada.");
    if (row.status === "sent") return json({ status: "sent" });

    const { data: claimed, error } = await admin.rpc("claim_customer_whatsapp_outbox_item", { p_id: outboxId });
    if (error) throw new HttpError(500, "Não foi possível preparar o envio.");
    const rows = (claimed ?? []) as OutboxRow[];
    if (!rows.length) return json({ status: row.status, error: row.last_error || "" });
    const [result] = await deliver(admin, rows);
    return json({ status: result.status, error: result.error ?? "" });
  } catch (error) {
    return handleError("whatsapp-send", error);
  }
});
