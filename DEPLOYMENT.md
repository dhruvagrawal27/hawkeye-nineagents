# HAWKEYE — Deployment

> ⚠️ **Read [DEPLOYMENT_RETRO.md](DEPLOYMENT_RETRO.md) first** if you're going to provision a fresh instance — it captures every gotcha we hit on the live deploy with the permanent fixes already merged. Total time saved: ~2.5 hours.

---

## 🟢 Currently deployed

| | |
|---|---|
| **Live URL** | https://hawkeye.nineagents.in |
| **Deployed at** | 2026-05-09 |
| **VPS** | Hetzner Cloud · CX33 (4 vCPU / 8 GB RAM / 80 GB SSD) · Helsinki (HEL1) |
| **Public IP** | 204.168.183.139 |
| **OS** | Ubuntu 24.04 LTS |
| **Cost** | **~€8/mo** (CX33 only) |
| **Backups** | ❌ NOT enabled — cost decision. Snapshots can be enabled in the Hetzner console for an additional ~€1.60/mo (20% surcharge). For demo data this is fine; before any real-data deployment, turn them on. |
| **TLS** | Let's Encrypt cert valid until 2026-08-07, auto-renewing via `certbot.timer` |
| **DNS** | Hostinger nameservers (`ns1/2.dns-parking.com`); A record `hawkeye → 204.168.183.139` |
| **Backend auth state** | `PREFLIGHT_MODE=1` — JWT auth bypassed for demo. Anyone with the URL can browse. Switch role with the chip in the top-right. **Flip to `0`** in `/opt/hawkeye/.env` and `docker compose restart backend` to lock down for production (then frontend Keycloak login flow is required, which is on the [NEXT_STEPS](NEXT_STEPS.md) list). |
| **Auto-deploy** | GitHub Actions secrets `VPS_HOST` + `VPS_SSH_KEY` set; variable `DEPLOY_ENABLED=true`. Every push to `main` runs `deploy.sh` over SSH. Warm deploy: ~3 min. |
| **Demo creds** | (only used when `PREFLIGHT_MODE=0`) `analyst@hawkeye.local` / `analyst` and `supervisor@hawkeye.local` / `supervisor` — pre-loaded from `infra/keycloak/realm-export.json` |

---

## Deployment recipe (fresh VPS)

The recipe below is what you'd run on a NEW Hetzner CX33 (or any 8 GB Ubuntu 24.04 box). The current production box was provisioned this way on 2026-05-09.

> 📋 **Before you start**, read [DEPLOYMENT_RETRO.md](DEPLOYMENT_RETRO.md). The fixes are all already in `main`, but knowing where the landmines were makes the deploy faster.

## 1. DNS (do this first; TLS depends on it)

⚠️ **Critical pre-check**: confirm the domain's authoritative nameservers point ONLY at the DNS provider you'll be editing. If your domain is delegated to multiple providers (e.g. both Hostinger AND Vercel), DNS resolvers round-robin and you'll get inconsistent answers. We hit this — see RETRO #7.

```bash
dig +short NS nineagents.in
# Should show ONE provider's nameservers (e.g. ns1/2.dns-parking.com only)
```

At the registrar for `nineagents.in`:

```
hawkeye.nineagents.in   A   <new-vps-ip>   TTL 300
```

Wait for propagation: `dig +short hawkeye.nineagents.in @8.8.8.8` should return your VPS IP.

## 2. One-time host bootstrap

At the registrar for `nineagents.in`:

```
hawkeye.nineagents.in   A   <new-vps-ip>   TTL 300
```

Wait for propagation: `dig +short hawkeye.nineagents.in` should return your VPS IP.

## 2. One-time host bootstrap

```bash
scp deploy/bootstrap-vps.sh root@<vps-ip>:/root/
ssh root@<vps-ip> "chmod +x /root/bootstrap-vps.sh && /root/bootstrap-vps.sh"
```

The bootstrap script installs Docker, nginx, certbot, creates `/opt/hawkeye-data/` directories with `chmod 700`, and configures ufw to allow only 22/80/443.

## 3. Place artifacts and synthetic data

The repo gitignores `*.parquet` and `*.txt` model files. Upload them to the host:

```bash
ssh root@<vps-ip> "mkdir -p /opt/hawkeye-data/{artifacts,synthetic}"
scp artifacts/* root@<vps-ip>:/opt/hawkeye-data/artifacts/
scp data/*       root@<vps-ip>:/opt/hawkeye-data/synthetic/
```

Verify on the host:
```bash
ls -la /opt/hawkeye-data/artifacts/   # 6 files: 2 .txt models, 2 .parquet, 2 .json
ls -la /opt/hawkeye-data/synthetic/   # 5 files including synthetic_events.jsonl
```

## 4. Clone repo and create `.env`

```bash
ssh root@<vps-ip>
git clone https://github.com/dhruvagrawal27/hawkeye-nineagents /opt/hawkeye
cd /opt/hawkeye
cp .env.example .env
chmod 600 .env
nano .env
```

Fill these values minimum:

| Variable | Value |
|---|---|
| `PUBLIC_BASE_URL` | `https://hawkeye.nineagents.in` |
| `GROQ_API_KEY` | your Groq key (get one at console.groq.com) |
| `POSTGRES_PASSWORD` | strong random |
| `NEO4J_PASS` | strong random |
| `MINIO_SECRET_KEY` | strong random |
| `KEYCLOAK_ADMIN_PASSWORD` | strong random |

Generate randoms with `openssl rand -base64 32`.

## 5. Install host nginx config + TLS

⚠️ The committed nginx config has hardcoded SSL cert paths (`/etc/letsencrypt/live/hawkeye.nineagents.in/...`) — `nginx -t` will fail before the cert exists. Use this 2-step flow:

### 5a — minimal HTTP-only config so nginx starts (and serves the ACME challenge)

```bash
rm -f /etc/nginx/sites-enabled/default
mkdir -p /var/www/certbot

cat > /etc/nginx/sites-available/hawkeye.nineagents.in <<'HAWKEYE_NGINX_EOF'
server {
    listen 80;
    server_name hawkeye.nineagents.in;
    location /.well-known/acme-challenge/ { root /var/www/certbot; }
    location / { return 200 "HAWKEYE provisioning - TLS pending\n"; add_header Content-Type text/plain; }
}
HAWKEYE_NGINX_EOF

ln -sfn /etc/nginx/sites-available/hawkeye.nineagents.in /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
```

Verify nginx is reachable on the public IP via the actual hostname (use `--resolve` to bypass any DNS oddities):

```bash
curl --resolve hawkeye.nineagents.in:80:$(hostname -I | awk '{print $1}') http://hawkeye.nineagents.in/
# Should print: HAWKEYE provisioning - TLS pending
```

### 5b — issue cert via webroot (no nginx -t conflict)

```bash
certbot certonly --webroot -w /var/www/certbot \
  -d hawkeye.nineagents.in \
  --email dhruv@nineagents.in \
  --agree-tos --no-eff-email --non-interactive

ls -la /etc/letsencrypt/live/hawkeye.nineagents.in/
# expect: cert.pem, chain.pem, fullchain.pem, privkey.pem
```

### 5c — swap in the FULL nginx config (now that the cert exists)

```bash
cp /opt/hawkeye/infra/nginx/hawkeye.nineagents.in.conf /etc/nginx/sites-available/hawkeye.nineagents.in
nginx -t && systemctl reload nginx

# Verify auto-renewal works (dry run; doesn't change the real cert)
certbot renew --dry-run
```

### 5d — verify HTTPS from your laptop

```powershell
# Use curl.exe explicitly — PowerShell aliases `curl` to Invoke-WebRequest which doesn't take Unix flags
curl.exe -I http://hawkeye.nineagents.in/                # should be 301 to HTTPS
curl.exe https://hawkeye.nineagents.in/api/healthz       # {"status":"ok"}
start https://hawkeye.nineagents.in
```

## 6. First deploy

```bash
cd /opt/hawkeye
deploy/deploy.sh
```

This pulls/builds compose, waits for backend health, runs migrations, runs the seed script, runs `preflight_check.py`, and reloads nginx. **If preflight fails, the deploy fails.**

## 7. Hook up CI/CD (GitHub Actions)

In the GitHub repo settings → Secrets and variables → Actions, set:

| Secret | Value |
|---|---|
| `VPS_HOST` | the VPS IP |
| `VPS_SSH_KEY` | ed25519 private key (the matching public key must be in `/root/.ssh/authorized_keys` on the VPS) |

Subsequent pushes to `main` auto-deploy via `.github/workflows/deploy.yml`.

## SSH tunnels for admin UIs

All admin ports bind to `127.0.0.1` on the VPS. To access from your laptop:

```bash
# Grafana
ssh -N -L 3000:127.0.0.1:3000 root@<vps-ip>
# then open http://localhost:3000  (admin / value of GRAFANA_ADMIN_PASSWORD)

# Neo4j Browser
ssh -N -L 7474:127.0.0.1:7474 -L 7687:127.0.0.1:7687 root@<vps-ip>
# then open http://localhost:7474

# Prometheus
ssh -N -L 9090:127.0.0.1:9090 root@<vps-ip>
# then open http://localhost:9090

# Keycloak admin
ssh -N -L 8081:127.0.0.1:8081 root@<vps-ip>
# then open http://localhost:8081/admin   (admin / value of KEYCLOAK_ADMIN_PASSWORD)

# MinIO console
ssh -N -L 9001:127.0.0.1:9001 root@<vps-ip>
# then open http://localhost:9001
```

## Backups

Two things must be backed up:

```bash
# Postgres logical backup (alerts, narratives, audit log)
docker compose exec -T postgres pg_dump -U hawkeye hawkeye | gzip > backup_postgres_$(date +%F).sql.gz

# Neo4j graph (employee→system access counts)
docker compose exec -T neo4j neo4j-admin database dump neo4j \
  --to-path=/var/lib/neo4j/dumps
docker cp $(docker compose ps -q neo4j):/var/lib/neo4j/dumps/neo4j.dump backup_neo4j_$(date +%F).dump
```

Cron suggestion: nightly to `/opt/hawkeye-backups/`, weekly to off-host.

## Updating after a deploy

```bash
cd /opt/hawkeye
git pull
deploy/deploy.sh
```

GitHub Actions does this automatically on push to `main`. Manual run only if CI is broken.

## Rolling back

```bash
cd /opt/hawkeye
git log --oneline -10                    # find target SHA
git reset --hard <sha>
deploy/deploy.sh                         # re-deploys
```

The compose images are tagged with the commit SHA, so rolling back the git checkout rolls back the binary.

## Troubleshooting

| Symptom | Likely cause | Action |
|---|---|---|
| `make up` hangs at backend healthz | Postgres init slow on first boot | Wait 90s, then `docker compose logs backend` |
| `preflight_check.py` fails on `groq_narrative` | `GROQ_API_KEY` not set or wrong | Check `.env`, restart backend |
| `preflight_check.py` fails on `replay_produces_alerts` | Consumer not consuming or threshold too high | `docker compose logs backend \| grep -i replay`; verify Kafka up |
| 502 Bad Gateway from nginx | Backend container unhealthy | `docker compose ps`; restart backend |
| Cert expired | Certbot renew failed | `certbot renew --force-renewal` and `systemctl reload nginx` |

## Hardware sizing

| Component | Min | Rec |
|---|---|---|
| vCPU | 4 | 8 |
| RAM | 8 GB | 16 GB |
| Disk | 80 GB SSD | 160 GB SSD |

Kafka + Neo4j + Keycloak together pull ~4 GB RAM steady. The backend with two LightGBM models loaded uses ~700 MB. Frontend nginx is negligible.
