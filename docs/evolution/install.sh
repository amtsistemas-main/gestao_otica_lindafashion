#!/usr/bin/env bash
# Instalação do gateway Evolution API (WhatsApp) numa VPS Ubuntu — Hostinger ou similar.
# Uso (no terminal da VPS, como root):
#   bash install.sh wa.seudominio.com.br
# O script instala o Docker, gera as chaves, escolhe a versão estável mais recente do
# Evolution v2, sobe Evolution + Postgres + Redis + Caddy (HTTPS automático) e, no fim,
# mostra a URL e a chave para configurar no Supabase. Pode ser executado de novo com segurança.
set -euo pipefail

DOMAIN="${1:-}"
if [[ -z "$DOMAIN" ]]; then
  echo "Informe o subdomínio: bash install.sh wa.seudominio.com.br" >&2
  exit 1
fi
if [[ $EUID -ne 0 ]]; then
  echo "Execute como root (ou com sudo)." >&2
  exit 1
fi

DIR=/opt/evolution
mkdir -p "$DIR"
cd "$DIR"

echo "==> Atualizando o sistema e instalando o Docker"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y >/dev/null
apt-get install -y curl ca-certificates openssl python3 >/dev/null
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh >/dev/null
fi
systemctl enable --now docker >/dev/null

echo "==> Liberando as portas 80 e 443 (se houver firewall local)"
if command -v ufw >/dev/null 2>&1 && ufw status | grep -q "Status: active"; then
  ufw allow 22/tcp >/dev/null; ufw allow 80/tcp >/dev/null; ufw allow 443/tcp >/dev/null
fi

echo "==> Escolhendo a versão do Evolution API"
VERSION="$(curl -fsS 'https://hub.docker.com/v2/repositories/evoapicloud/evolution-api/tags?page_size=100' 2>/dev/null | python3 -c '
import json, re, sys
try:
    tags = [t["name"] for t in json.load(sys.stdin).get("results", [])]
except Exception:
    tags = []
stable = [t for t in tags if re.fullmatch(r"v2\.\d+\.\d+", t)]
stable.sort(key=lambda t: tuple(int(p) for p in t[1:].split(".")))
print(stable[-1] if stable else "")
' || true)"
VERSION="${VERSION:-v2.2.3}"
echo "    versão: $VERSION"

if [[ ! -f .env ]]; then
  echo "==> Gerando chaves"
  cat > .env <<EOF
EVOLUTION_DOMAIN=$DOMAIN
EVOLUTION_VERSION=$VERSION
EVOLUTION_API_KEY=$(openssl rand -hex 32)
POSTGRES_PASSWORD=$(openssl rand -hex 24)
EOF
  chmod 600 .env
else
  echo "==> Mantendo as chaves existentes (.env)"
  sed -i "s/^EVOLUTION_DOMAIN=.*/EVOLUTION_DOMAIN=$DOMAIN/" .env
fi

cat > Caddyfile <<'EOF'
{$EVOLUTION_DOMAIN} {
	encode gzip
	@manager path /manager*
	respond @manager 404
	reverse_proxy evolution:8080
}
EOF

cat > docker-compose.yml <<'EOF'
services:
  evolution:
    image: evoapicloud/evolution-api:${EVOLUTION_VERSION}
    restart: unless-stopped
    environment:
      SERVER_URL: https://${EVOLUTION_DOMAIN}
      DATABASE_ENABLED: "true"
      DATABASE_PROVIDER: postgresql
      DATABASE_CONNECTION_URI: postgresql://evolution:${POSTGRES_PASSWORD}@postgres:5432/evolution?schema=public
      DATABASE_SAVE_DATA_INSTANCE: "true"
      DATABASE_SAVE_DATA_NEW_MESSAGE: "false"
      DATABASE_SAVE_MESSAGE_UPDATE: "false"
      DATABASE_SAVE_DATA_CONTACTS: "false"
      DATABASE_SAVE_DATA_CHATS: "false"
      CACHE_REDIS_ENABLED: "true"
      CACHE_REDIS_URI: redis://redis:6379/6
      CACHE_LOCAL_ENABLED: "false"
      AUTHENTICATION_API_KEY: ${EVOLUTION_API_KEY}
      AUTHENTICATION_EXPOSE_IN_FETCH_INSTANCES: "false"
      DEL_INSTANCE: "false"
      QRCODE_LIMIT: "10"
      WEBHOOK_GLOBAL_ENABLED: "false"
      LOG_LEVEL: ERROR,WARN
    volumes:
      - evolution_instances:/evolution/instances
    depends_on: [postgres, redis]
    networks: [internal]
  postgres:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_USER: evolution
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: evolution
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks: [internal]
  redis:
    image: redis:7-alpine
    restart: unless-stopped
    command: ["redis-server", "--appendonly", "yes"]
    volumes:
      - redis_data:/data
    networks: [internal]
  caddy:
    image: caddy:2-alpine
    restart: unless-stopped
    ports: ["80:80", "443:443"]
    environment:
      EVOLUTION_DOMAIN: ${EVOLUTION_DOMAIN}
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
    depends_on: [evolution]
    networks: [internal]
volumes:
  evolution_instances:
  postgres_data:
  redis_data:
  caddy_data:
networks:
  internal:
EOF

echo "==> Backup diário do banco do gateway (03:00, mantém 14 dias)"
mkdir -p "$DIR/backups"
cat > /etc/cron.d/evolution-backup <<EOF
0 3 * * * root cd $DIR && docker compose exec -T postgres pg_dump -U evolution evolution | gzip > $DIR/backups/evolution-\$(date +\%F).sql.gz && find $DIR/backups -name '*.sql.gz' -mtime +14 -delete
EOF

echo "==> Subindo os serviços (o primeiro download leva alguns minutos)"
docker compose pull -q
docker compose up -d

echo "==> Aguardando o HTTPS de https://$DOMAIN"
for _ in $(seq 1 30); do
  if curl -fsS "https://$DOMAIN/" >/dev/null 2>&1; then break; fi
  sleep 5
done

API_KEY="$(grep '^EVOLUTION_API_KEY=' .env | cut -d= -f2)"
echo
if curl -fsS "https://$DOMAIN/" >/dev/null 2>&1; then
  echo "✅ Evolution API no ar: https://$DOMAIN"
else
  echo "⚠️  O HTTPS ainda não respondeu. Confira se o registro DNS A de $DOMAIN aponta para este servidor"
  echo "    e se as portas 80/443 estão liberadas no firewall da Hostinger; depois rode: cd $DIR && docker compose logs caddy"
fi
echo
echo "Configure no Supabase (no PowerShell, na pasta do projeto):"
echo "  npx supabase secrets set EVOLUTION_API_URL=https://$DOMAIN EVOLUTION_API_KEY=$API_KEY --project-ref swlccwcykxmvwptzxrxt"
echo
echo "Guarde a chave acima em local seguro (ela também está em $DIR/.env)."
