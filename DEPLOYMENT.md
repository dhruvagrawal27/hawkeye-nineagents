# HAWKEYE — Deployment

Production target: a fresh Hetzner CCX23 (or equivalent) Ubuntu 22.04 LTS VPS. Domain: `hawkeye.nineagents.in`.

## 1. DNS (do this first; TLS depends on it)

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

```bash
cp /opt/hawkeye/infra/nginx/hawkeye.nineagents.in.conf /etc/nginx/sites-available/
ln -sfn /etc/nginx/sites-available/hawkeye.nineagents.in /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

certbot --nginx -d hawkeye.nineagents.in \
  --email nineagents@nineagents.in --agree-tos --no-eff-email
certbot renew --dry-run
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
