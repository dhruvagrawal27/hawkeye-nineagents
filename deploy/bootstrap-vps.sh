#!/usr/bin/env bash
# HAWKEYE — one-time host bootstrap.
# Tested on Ubuntu 22.04 LTS (Hetzner CCX23).
# Run as root.
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Run as root." >&2
  exit 1
fi

echo "[1/5] Installing Docker..."
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
fi
systemctl enable --now docker

echo "[2/5] Installing nginx + certbot..."
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  nginx certbot python3-certbot-nginx \
  curl wget ufw fail2ban git
systemctl enable --now nginx

echo "[3/5] Provisioning data directories at /opt/hawkeye-data ..."
mkdir -p /opt/hawkeye-data/{postgres,neo4j/data,neo4j/logs,kafka/data,redis/data,minio/data,keycloak/data,mlflow,grafana,artifacts,synthetic,backups}
chmod 700 /opt/hawkeye-data

mkdir -p /opt/hawkeye
mkdir -p /var/www/certbot

echo "[4/5] Configuring firewall..."
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

echo "[5/5] Done. Next steps:"
cat <<'EOF'

  1. Point hawkeye.nineagents.in   A   <this VPS IP>   at the registrar.
  2. SCP your model artifacts:
       scp artifacts/* root@<vps>:/opt/hawkeye-data/artifacts/
       scp data/*       root@<vps>:/opt/hawkeye-data/synthetic/
  3. Clone the repo:
       git clone https://github.com/dhruvagrawal27/hawkeye-nineagents /opt/hawkeye
       cp /opt/hawkeye/.env.example /opt/hawkeye/.env
       chmod 600 /opt/hawkeye/.env
       nano /opt/hawkeye/.env   # fill GROQ_API_KEY, passwords, PUBLIC_BASE_URL
  4. Symlink the bind-mount targets:
       ln -sfn /opt/hawkeye-data/artifacts /opt/hawkeye/backend/artifacts
       ln -sfn /opt/hawkeye-data/synthetic /opt/hawkeye/backend/data
  5. Bring up the stack:
       cd /opt/hawkeye && deploy/deploy.sh
  6. Get TLS:
       cp /opt/hawkeye/infra/nginx/hawkeye.nineagents.in.conf /etc/nginx/sites-available/
       ln -sfn /etc/nginx/sites-available/hawkeye.nineagents.in /etc/nginx/sites-enabled/
       nginx -t && systemctl reload nginx
       certbot --nginx -d hawkeye.nineagents.in --email nineagents@nineagents.in --agree-tos --no-eff-email
  7. Add the deploy SSH key + GitHub Actions secrets (VPS_HOST, VPS_SSH_KEY).

EOF
