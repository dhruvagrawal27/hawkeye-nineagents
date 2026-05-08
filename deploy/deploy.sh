#!/usr/bin/env bash
# HAWKEYE — idempotent deploy script.
# Called by GitHub Actions deploy workflow on every push to main.
# Manual invocation:  ssh root@<vps> "/opt/hawkeye/deploy/deploy.sh"
set -euo pipefail

REPO_DIR="${REPO_DIR:-/opt/hawkeye}"
COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml"

cd "$REPO_DIR"

echo "[deploy] git fetch + reset..."
git fetch --all --prune
git reset --hard origin/main

echo "[deploy] symlinking bind-mount targets..."
ln -sfn /opt/hawkeye-data/artifacts backend/artifacts
ln -sfn /opt/hawkeye-data/synthetic  backend/data

echo "[deploy] docker compose build..."
$COMPOSE pull --quiet || true
$COMPOSE build

echo "[deploy] docker compose up..."
$COMPOSE up -d --remove-orphans

echo "[deploy] waiting for backend healthz..."
for i in $(seq 1 90); do
    if curl -sf http://127.0.0.1:8000/healthz >/dev/null 2>&1; then
        break
    fi
    if [ "$i" -eq 90 ]; then
        echo "[deploy] TIMEOUT: backend never became healthy" >&2
        $COMPOSE logs --tail=200 backend
        exit 1
    fi
    sleep 2
done

echo "[deploy] alembic upgrade head..."
$COMPOSE exec -T backend alembic upgrade head

echo "[deploy] seeding..."
$COMPOSE exec -T backend python -m app.scripts.seed

echo "[deploy] running preflight (deploy fails if this fails)..."
$COMPOSE exec -T -e PREFLIGHT_MODE=1 backend python -m app.scripts.preflight_check

echo "[deploy] reloading host nginx..."
if [ -f /etc/nginx/sites-enabled/hawkeye.nineagents.in ]; then
  nginx -t && systemctl reload nginx
fi

echo "[deploy] SUCCESS"
