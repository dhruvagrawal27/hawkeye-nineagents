# HAWKEYE — Quickstart

> 🟢 The system is **already live** at <https://hawkeye.nineagents.in>. If you're an evaluator, just open the URL — no setup required, auth is bypassed for the demo.

This file is for **developers** who want to run HAWKEYE locally OR re-deploy to their own infrastructure.

## Local (the stack you have right now)

```bash
# 0. Prerequisites — already met:
#    Docker Desktop running on Windows/macOS
#    Python 3.11 venv at .venv/  (only needed for ad-hoc dev)
#    .env present with GROQ_API_KEY

# 1. Build images (~10 min on first run, ~30s after)
docker compose build

# 2. Start the full stack (12 services)
docker compose up -d

# 3. Wait until backend is healthy (~60s)
docker compose ps

# 4. Run migrations + seed Postgres + Redis + Neo4j
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.scripts.seed

# 5. Verify everything end-to-end (must show "10 passed, 0 failed")
docker compose exec backend python -m app.scripts.preflight_check

# 6. Open the dashboard
#    http://localhost:8080      (frontend)
#    http://localhost:8000/docs (backend OpenAPI)
```

### Trigger a live demo

```bash
# Start replay (mule_burst mode — alerts fire within 30-60s)
curl -X POST -H "content-type: application/json" \
  -d '{"mode":"mule_burst","rate":500}' \
  http://localhost:8000/replay/start

# Watch alerts fire in the terminal
docker compose logs -f backend | grep ALERT.created

# Or open Replay Studio in the UI: http://localhost:8080/replay
# Click "Inject mule burst" — 3+ alerts within 10s.

# Stop replay
curl -X POST http://localhost:8000/replay/stop
```

### Tear down / reset

```bash
docker compose down                # stop, keep volumes (data persists)
docker compose down -v             # stop + wipe all volumes (clean slate)
```

## Production deploy (Hetzner VPS)

When you're ready to publish at `https://hawkeye.nineagents.in`:

```bash
# On your laptop:
git push origin main

# On the VPS, one-time setup (root):
ssh root@<vps-ip>
curl -O https://raw.githubusercontent.com/dhruvagrawal27/hawkeye-nineagents/main/deploy/bootstrap-vps.sh
chmod +x bootstrap-vps.sh
./bootstrap-vps.sh

# Upload artifacts (model files + synthetic events; gitignored from repo)
# From your laptop:
scp artifacts/* root@<vps-ip>:/opt/hawkeye-data/artifacts/
scp data/*       root@<vps-ip>:/opt/hawkeye-data/synthetic/

# DNS
# At your nineagents.in registrar:
#   hawkeye.nineagents.in   A   <vps-ip>   TTL 300

# On VPS:
git clone https://github.com/dhruvagrawal27/hawkeye-nineagents /opt/hawkeye
cd /opt/hawkeye
cp .env.example .env
chmod 600 .env
nano .env     # fill: GROQ_API_KEY, POSTGRES_PASSWORD, NEO4J_PASS,
              #       MINIO_SECRET_KEY, KEYCLOAK_ADMIN_PASSWORD, GRAFANA_ADMIN_PASSWORD
              # set: PUBLIC_BASE_URL=https://hawkeye.nineagents.in
              # set: PREFLIGHT_MODE=0  (production-safe)

# Symlink artifacts/data into the repo so compose finds them
ln -sfn /opt/hawkeye-data/artifacts /opt/hawkeye/artifacts
ln -sfn /opt/hawkeye-data/synthetic /opt/hawkeye/data

# First deploy
cd /opt/hawkeye
deploy/deploy.sh

# Host nginx + TLS
cp infra/nginx/hawkeye.nineagents.in.conf /etc/nginx/sites-available/
ln -sfn /etc/nginx/sites-available/hawkeye.nineagents.in /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
certbot --nginx -d hawkeye.nineagents.in \
  --email nineagents@nineagents.in --agree-tos --no-eff-email

# Add GitHub Actions secrets:
#   VPS_HOST       = <vps-ip>
#   VPS_SSH_KEY    = ed25519 private key (matching public key in /root/.ssh/authorized_keys)
# Subsequent pushes to main auto-deploy.
```

See `DEPLOYMENT.md` for the full reference (SSH tunnels, backup commands, troubleshooting).

## Test credentials

```
analyst@hawkeye.local   / analyst       (read alerts, triage, view graph)
supervisor@hawkeye.local / supervisor    (above + escalate, regenerate narrative)
```

These are loaded from `infra/keycloak/realm-export.json`. In local dev with `PREFLIGHT_MODE=1`, JWT is bypassed and you don't need to log in via Keycloak — just open `http://localhost:8080` and the dashboard loads directly.
