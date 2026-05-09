#!/usr/bin/env bash
# HAWKEYE — idempotent deploy script.
# Called by GitHub Actions deploy workflow on every push to main.
# Manual invocation:  ssh root@<vps> "/opt/hawkeye/deploy/deploy.sh"
set -euo pipefail

REPO_DIR="${REPO_DIR:-/opt/hawkeye}"
DATA_DIR="${DATA_DIR:-/opt/hawkeye-data}"
COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml"

cd "$REPO_DIR"

echo "[deploy] git fetch + reset..."
git fetch --all --prune
git reset --hard origin/main

# After git reset, the repo's artifacts/ and data/ directories exist again
# (they hold feature_config.json + synthesis_metadata.json which ARE
# committed). Compose binds them as ./artifacts and ./data, so we replace
# them with symlinks pointing at the host's persistent data volume.
echo "[deploy] symlinking artifacts + data into host data dir..."
rm -rf artifacts data
ln -sfn "$DATA_DIR/artifacts" artifacts
ln -sfn "$DATA_DIR/synthetic" data

# Sanity check — both targets must exist and contain the model files
if [ ! -f artifacts/lgb_model_m1_full.txt ] || [ ! -f data/synthetic_events.jsonl ]; then
    echo "[deploy] FATAL: $DATA_DIR is missing model artifacts or synthetic data."
    echo "         scp them up before running deploy:"
    echo "           scp artifacts/* root@<vps>:$DATA_DIR/artifacts/"
    echo "           scp data/*       root@<vps>:$DATA_DIR/synthetic/"
    exit 1
fi

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

echo "[deploy] seeding (idempotent — skipped if alerts already populated)..."
$COMPOSE exec -T backend python -m app.scripts.seed

echo "[deploy] running preflight (deploy fails if this fails)..."
$COMPOSE exec -T backend python -m app.scripts.preflight_check

echo "[deploy] reloading host nginx (skipped if config not yet installed)..."
if [ -f /etc/nginx/sites-enabled/hawkeye.nineagents.in ]; then
  nginx -t && systemctl reload nginx
else
  echo "[deploy]   (no nginx site enabled yet — install it manually after first deploy:"
  echo "           cp infra/nginx/hawkeye.nineagents.in.conf /etc/nginx/sites-available/"
  echo "           ln -sfn /etc/nginx/sites-available/hawkeye.nineagents.in /etc/nginx/sites-enabled/"
  echo "           nginx -t && systemctl reload nginx"
  echo "           certbot --nginx -d hawkeye.nineagents.in --email dhruv@nineagents.in --agree-tos --no-eff-email"
  echo "           )"
fi

echo "[deploy] SUCCESS"
