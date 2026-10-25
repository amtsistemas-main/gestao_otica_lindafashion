import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient, type SupabaseClient } from "npm:@supabase/supabase-js@2";

// Gestão de logins da loja (multilogin). A chave de serviço existe somente aqui, no
// servidor; o aplicativo desktop envia apenas o token do usuário conectado.
//
// Regras:
// - somente donos e administradores ativos da organização usam esta função;
// - somente o dono cria ou promove administradores;
// - ninguém altera o dono por aqui, nem o próprio papel/situação;
// - administradores não alteram outros administradores.

const MODULES = [
  "vendas", "clientes", "relacionamento", "produtos", "estoque", "fornecedores",
  "financeiro", "indicadores", "analises", "configuracoes",
];
const ROLES = ["admin", "member"];
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
const BANNED_FOREVER = "876000h";

type Member = {
  user_id: string;
  organization_id: string;
  role: string;
  active: boolean;
  display_name: string;
  email: string;
  allowed_modules: string[] | null;
  created_at: string;
};

class HttpError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", "cache-control": "no-store" },
  });

function cleanModules(value: unknown): string[] | null {
  if (value === null || value === undefined) return null;
  if (!Array.isArray(value)) throw new HttpError(400, "Lista de módulos inválida.");
  const unique = [...new Set(value.map((item) => String(item)))];
  const invalid = unique.filter((item) => !MODULES.includes(item));
  if (invalid.length) throw new HttpError(400, `Módulo desconhecido: ${invalid.join(", ")}.`);
  return unique;
}

function cleanText(value: unknown, max: number): string {
  return String(value ?? "").trim().slice(0, max);
}

function checkPassword(value: unknown): string {
  const password = String(value ?? "");
  if (password.length < 8) throw new HttpError(400, "A senha precisa ter pelo menos 8 caracteres.");
  if (password.length > 72) throw new HttpError(400, "A senha pode ter no máximo 72 caracteres.");
  return password;
}

async function loadMember(admin: SupabaseClient, org: string, userId: string): Promise<Member> {
  const { data, error } = await admin.from("organization_members")
    .select("user_id, organization_id, role, active, display_name, email, allowed_modules, created_at")
    .eq("organization_id", org).eq("user_id", userId).maybeSingle();
  if (error) throw new HttpError(500, "Não foi possível consultar o usuário.");
  if (!data) throw new HttpError(404, "Usuário não encontrado nesta organização.");
  return data as Member;
}

function assertCanManage(caller: Member, target: Member) {
  if (target.role === "owner") throw new HttpError(403, "O dono da loja não pode ser alterado por aqui.");
  if (caller.role === "admin" && target.role === "admin" && target.user_id !== caller.user_id) {
    throw new HttpError(403, "Somente o dono pode alterar outro administrador.");
  }
}

Deno.serve(async (req: Request) => {
  if (req.method !== "POST") return json({ error: "Método não permitido." }, 405);
  const url = Deno.env.get("SUPABASE_URL");
  const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!url || !serviceKey) return json({ error: "Configuração do servidor incompleta." }, 500);

  const admin = createClient(url, serviceKey, { auth: { persistSession: false, autoRefreshToken: false } });
  try {
    const token = (req.headers.get("Authorization") ?? "").replace(/^Bearer\s+/i, "").trim();
    if (!token) throw new HttpError(401, "Sessão obrigatória.");
    const { data: auth, error: authError } = await admin.auth.getUser(token);
    if (authError || !auth?.user) throw new HttpError(401, "Sessão inválida ou expirada. Entre novamente.");

    const body = await req.json().catch(() => null) as Record<string, unknown> | null;
    if (!body) throw new HttpError(400, "Requisição inválida.");
    const action = String(body.action ?? "");
    const org = String(body.organization_id ?? "");
    if (!org) throw new HttpError(400, "Organização não informada.");

    const caller = await loadMember(admin, org, auth.user.id).catch(() => {
      throw new HttpError(403, "Usuário sem vínculo com esta organização.");
    });
    if (!caller.active || !["owner", "admin"].includes(caller.role)) {
      throw new HttpError(403, "Somente donos e administradores gerenciam usuários.");
    }

    if (action === "list") {
      const { data, error } = await admin.from("organization_members")
        .select("user_id, role, active, display_name, email, allowed_modules, created_at")
        .eq("organization_id", org).order("created_at");
      if (error) throw new HttpError(500, "Não foi possível listar os usuários.");
      const members = await Promise.all((data ?? []).map(async (member) => {
        const { data: user } = await admin.auth.admin.getUserById(member.user_id);
        return {
          ...member,
          email: member.email || user?.user?.email || "",
          last_sign_in_at: user?.user?.last_sign_in_at ?? null,
        };
      }));
      return json({ members });
    }

    if (action === "create") {
      const email = cleanText(body.email, 160).toLowerCase();
      if (!EMAIL_RE.test(email)) throw new HttpError(400, "Informe um e-mail válido.");
      const password = checkPassword(body.password);
      const displayName = cleanText(body.display_name, 80);
      if (!displayName) throw new HttpError(400, "Informe o nome do usuário.");
      const role = String(body.role ?? "member");
      if (!ROLES.includes(role)) throw new HttpError(400, "Perfil inválido.");
      if (role === "admin" && caller.role !== "owner") {
        throw new HttpError(403, "Somente o dono pode criar administradores.");
      }
      const modules = role === "admin" ? null : cleanModules(body.allowed_modules ?? []);

      const { data: created, error: createError } = await admin.auth.admin.createUser({
        email, password, email_confirm: true, user_metadata: { display_name: displayName },
      });
      if (createError || !created?.user) {
        const message = String(createError?.message ?? "");
        if (/already|registered|exists/i.test(message)) {
          throw new HttpError(409, "Já existe um login com este e-mail.");
        }
        throw new HttpError(400, "Não foi possível criar o login. Verifique o e-mail e a senha.");
      }
      const { error: memberError } = await admin.from("organization_members").insert({
        organization_id: org, user_id: created.user.id, role, active: true,
        display_name: displayName, email, allowed_modules: modules,
      });
      if (memberError) {
        // Sem vínculo, o login não serviria para nada: desfaz a criação.
        await admin.auth.admin.deleteUser(created.user.id);
        throw new HttpError(500, "Não foi possível vincular o usuário à loja. Nada foi criado.");
      }
      return json({ user_id: created.user.id, email, role, allowed_modules: modules }, 201);
    }

    const userId = String(body.user_id ?? "");
    if (!userId) throw new HttpError(400, "Usuário não informado.");
    const target = await loadMember(admin, org, userId);

    if (action === "update") {
      assertCanManage(caller, target);
      const changes: Record<string, unknown> = {};
      if ("display_name" in body) {
        const name = cleanText(body.display_name, 80);
        if (!name) throw new HttpError(400, "Informe o nome do usuário.");
        changes.display_name = name;
      }
      if ("role" in body && body.role !== target.role) {
        const role = String(body.role);
        if (!ROLES.includes(role)) throw new HttpError(400, "Perfil inválido.");
        if (caller.role !== "owner") throw new HttpError(403, "Somente o dono altera o perfil de acesso.");
        if (target.user_id === caller.user_id) throw new HttpError(403, "Você não pode alterar o seu próprio perfil.");
        changes.role = role;
      }
      const finalRole = String(changes.role ?? target.role);
      if ("allowed_modules" in body || finalRole === "admin") {
        changes.allowed_modules = finalRole === "admin" ? null : cleanModules(body.allowed_modules ?? []);
      }
      if ("active" in body && Boolean(body.active) !== target.active) {
        if (target.user_id === caller.user_id) throw new HttpError(403, "Você não pode desativar o seu próprio acesso.");
        changes.active = Boolean(body.active);
      }
      if (Object.keys(changes).length) {
        const { error } = await admin.from("organization_members").update(changes)
          .eq("organization_id", org).eq("user_id", userId);
        if (error) throw new HttpError(500, "Não foi possível salvar as alterações.");
      }
      if ("active" in changes) {
        // Usuário desativado também não consegue mais entrar no aplicativo.
        await admin.auth.admin.updateUserById(userId, { ban_duration: changes.active ? "none" : BANNED_FOREVER });
      }
      return json({ ok: true, changes });
    }

    if (action === "reset_password") {
      assertCanManage(caller, target);
      const password = checkPassword(body.password);
      const { error } = await admin.auth.admin.updateUserById(userId, { password });
      if (error) throw new HttpError(400, "Não foi possível redefinir a senha.");
      return json({ ok: true });
    }

    throw new HttpError(400, "Ação desconhecida.");
  } catch (error) {
    if (error instanceof HttpError) return json({ error: error.message }, error.status);
    // Detalhes técnicos ficam fora da resposta; nenhum dado sensível é registrado.
    console.error("admin-users: erro inesperado", error instanceof Error ? error.name : "unknown");
    return json({ error: "Erro inesperado no servidor." }, 500);
  }
});
