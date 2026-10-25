import { createClient, type SupabaseClient } from "npm:@supabase/supabase-js@2";

export class HttpError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", "cache-control": "no-store" },
  });

export function adminClient(): SupabaseClient {
  const url = Deno.env.get("SUPABASE_URL");
  const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!url || !serviceKey) throw new HttpError(500, "Configuração do servidor incompleta.");
  return createClient(url, serviceKey, { auth: { persistSession: false, autoRefreshToken: false } });
}

export type Member = { user_id: string; role: string; active: boolean };

/** Signed-in caller and their active membership in the organization. */
export async function callerMember(admin: SupabaseClient, req: Request, organizationId: string): Promise<Member> {
  const token = (req.headers.get("Authorization") ?? "").replace(/^Bearer\s+/i, "").trim();
  if (!token) throw new HttpError(401, "Sessão obrigatória.");
  const { data: auth, error } = await admin.auth.getUser(token);
  if (error || !auth?.user) throw new HttpError(401, "Sessão inválida ou expirada. Entre novamente.");
  if (!organizationId) throw new HttpError(400, "Organização não informada.");
  const { data: member } = await admin.from("organization_members")
    .select("user_id, role, active").eq("organization_id", organizationId).eq("user_id", auth.user.id).maybeSingle();
  if (!member?.active) throw new HttpError(403, "Usuário sem vínculo ativo com esta organização.");
  return member as Member;
}

export function handleError(name: string, error: unknown): Response {
  if (error instanceof HttpError) return json({ error: error.message }, error.status);
  // Only the error class is logged: no tokens, numbers or message bodies.
  console.error(`${name}: erro inesperado`, error instanceof Error ? error.name : "unknown");
  return json({ error: "Erro inesperado no servidor." }, 500);
}

/** Constant-time string comparison for shared secrets. */
export function safeEqual(a: string, b: string): boolean {
  if (!a || !b || a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}
