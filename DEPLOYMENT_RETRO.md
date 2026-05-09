# Deployment retrospective — what went wrong on the first Hetzner deploy

A timeline of every issue we hit while deploying HAWKEYE to a fresh Hetzner CX33
on 2026-05-09, with the **symptom**, **root cause**, **immediate fix**, and
**permanent prevention** for each.

If you (or future-me) ever provision a second instance, read this first. The
problems below will not repeat — they're already fixed in `main` — but the
gotchas they expose are common to any 12-service compose deploy.

---

## Setup phase

### 1. `~/.ssh` directory didn't exist on Windows

**Symptom**
```
ssh-keygen ...
Saving key "C:\\Users\\dhruv\\.ssh\\hawkeye_deploy" failed: No such file or directory
```

**Root cause** — Fresh Windows install, never used SSH from PowerShell, so `~/.ssh` was never created.

**Fix** — `New-Item -ItemType Directory -Path $env:USERPROFILE\.ssh -Force` before keygen.

**Prevention** — Bake `New-Item -ItemType Directory -Path … -Force` into the keygen command for any first-time-on-Windows user. Already in the doc.

---

### 2. Bootstrap script ran cleanly — no issue. (Just a checkpoint.)

`curl | bash` worked first try. Docker, nginx, certbot, ufw all installed.

---

## Network + Docker phase

### 3. Symlinks created INSIDE the existing directory instead of replacing it

**Symptom** — After running `ln -sfn /opt/hawkeye-data/artifacts /opt/hawkeye/artifacts`:
```
/opt/hawkeye/artifacts/
├── artifacts → /opt/hawkeye-data/artifacts    (the symlink, NESTED)
├── feature_config.json                        (from the cloned repo)
└── feature_stats.json                         (from the cloned repo)
```
Compose then bound an empty/half-populated dir into the backend container.

**Root cause** — `ln -s SOURCE DEST` when DEST is an existing directory creates `DEST/<basename of SOURCE>` *inside* it, NOT at DEST. Our repo committed `artifacts/feature_config.json`, `artifacts/feature_stats.json`, `data/synthesis_metadata.json`, so the directories existed after `git clone`.

**Fix** — `rm -rf artifacts data` before the `ln -sfn`.

**Permanent prevention** — `deploy.sh` now does this:
```bash
rm -rf artifacts data
ln -sfn "$DATA_DIR/artifacts" artifacts
ln -sfn "$DATA_DIR/synthetic" data
```
Plus a sanity-fail if `lgb_model_m1_full.txt` or `synthetic_events.jsonl` aren't present after the symlink. (commit `d8c04c7`)

---

### 4. `chmod +x` was lost on every `git pull`

**Symptom**
```
./deploy/deploy.sh
-bash: ./deploy/deploy.sh: Permission denied
```
Worked once after `chmod +x`. Then `git pull` (to grab a fix) reset the mode back to `100644`, and the next run failed with the same error.

**Root cause** — Repo authored on Windows where `git config core.filemode false` is default. Git stored the scripts as `100644`, so any `git checkout` / `git reset --hard` (which `deploy.sh` itself does) restored the non-executable mode.

**Fix** — `chmod +x /opt/hawkeye/deploy/*.sh` after every pull.

**Permanent prevention** — `git update-index --chmod=+x deploy/*.sh infra/kafka/create-topics.sh` from a Linux git client (in our case, the dev container, but WSL also works). This changes the *tracked* mode in the index from `100644` to `100755`, persists across pulls, fixes the issue forever. (commit `bd2a9cd`)

---

### 5. Port 5000 collision (mlflow)

**Symptom**
```
Error response from daemon: failed to set up container networking: driver failed
programming external connectivity on endpoint hawkeye-mlflow-1: failed to bind
host port 127.0.0.1:5000/tcp: address already in use
```

**Root cause** — mlflow had partially started on a previous compose attempt (which failed at a different step). Its port-mapping survived in Docker's bookkeeping even though the container was gone. The real fix turned out to be issue #6 below (compose port-merge bug), but on the surface this looked like a stuck process.

**Fix** — `docker compose down` cleared the orphaned port mapping.

**Permanent prevention** — Issue #6 is the actual root cause (and is fixed). Also added a hint in `deploy.sh` to check `ss -tlnp` if a port collision recurs.

---

### 6. ⭐ Port 5432 collision — Compose v2 MERGES port arrays from overlay files instead of replacing

**Symptom** — Same as #5 but for postgres.
```
failed to bind host port 127.0.0.1:5432/tcp: address already in use
```
But nothing was on the port (`ss -tlnp | grep :5432` was empty before compose ran).

**Root cause** — `docker-compose.prod.yml` overrode `ports: ["127.0.0.1:5432:5432"]` thinking it would replace the dev `ports: ["5432:5432"]`. Compose v2 actually **merges** port arrays. Result: postgres tried to bind BOTH `0.0.0.0:5432` AND `127.0.0.1:5432` in the same container, second binding collided with the first.

**Fix attempt 1** — `!reset` YAML tag on the prod ports. This made things WORSE — the backend container ended up with NO host port mapping at all (`!reset` actually clears the property entirely; the list under it is ignored).

**Fix attempt 2** — `!override` YAML tag. Untested — switched to env var approach instead.

**Permanent fix** — Use env-var interpolation in the BASE compose file:
```yaml
ports:
  - "${BIND_HOST:-0.0.0.0}:5432:5432"
```
Local dev: `BIND_HOST` unset → defaults to `0.0.0.0` (host can connect via localhost).
Prod: `.env` has `BIND_HOST=127.0.0.1` → admin ports bound to loopback only.
`docker-compose.prod.yml` shrank to just `restart: unless-stopped` per service.
(commit `831f936`)

This works on every compose version, doesn't depend on the `!override` / `!reset` YAML tag spec.

---

## DNS + nginx + TLS phase

### 7. DNS resolved to wrong IP — nameservers were mixed (Vercel + Hostinger)

**Symptom**
```powershell
> Resolve-DnsName hawkeye.nineagents.in -Type A
hawkeye.nineagents.in   A   1800   216.198.79.1   ← Hostinger parking
hawkeye.nineagents.in   A   1800   216.198.79.65  ← Hostinger parking
```
The A record for `hawkeye → 204.168.183.139` had been added at Hostinger but the response showed something else.

**Root cause** — Domain had **both** sets of nameservers configured:
```
ns1.dns-parking.com    ← Hostinger
ns1.vercel-dns.com     ← Vercel (left over from another project)
ns2.dns-parking.com
ns2.vercel-dns.com
```
DNS resolvers round-robin between authoritative NS. Hostinger's panel had a yellow banner: *"Your domain's DNS records are currently managed elsewhere"* — which meant the panel was read-only and the A record never actually saved at Hostinger. Vercel's NS was answering (with whatever its DNS set returned).

**Fix** — Removed Vercel nameservers from Hostinger's "Change Nameservers" dialog, kept only `ns1/2.dns-parking.com`. Hostinger panel became writable. Added the A record. Verified with:
```bash
dig +short hawkeye.nineagents.in @ns1.dns-parking.com
# 204.168.183.139
```

**Permanent prevention** — Document in `DEPLOYMENT.md`: **"Before adding A records at any DNS panel, confirm the domain's authoritative nameservers point at that provider only."** Added to the DNS step in DEPLOYMENT.md. Also: prefer single-vendor DNS to avoid round-robin ambiguity.

---

### 8. VPS got "DEPLOYMENT_NOT_FOUND" from Vercel when curl'ing its own domain

**Symptom** — From the VPS shell:
```
$ curl http://hawkeye.nineagents.in/
The deployment could not be found on Vercel.
DEPLOYMENT_NOT_FOUND
```
Even though we'd configured nginx locally on the VPS.

**Root cause** — Same as #7 (mixed nameservers). The VPS's resolver got Vercel's IP for the domain. Request went to Vercel's edge, not back to the VPS.

**Fix** — Same fix as #7, plus we used `curl --resolve hawkeye.nineagents.in:80:204.168.183.139 …` in the meantime to bypass DNS and confirm nginx was working locally.

**Permanent prevention** — Added a "test nginx with `--resolve` before testing public DNS" step to the post-cert verification section in DEPLOYMENT.md.

---

### 9. Heredoc with embedded `# comments` got mangled when pasted into bash

**Symptom** — Pasting this block into the SSH terminal:
```bash
cat > /etc/nginx/sites-available/hawkeye.nineagents.in <<'EOF'
server {
    listen 80;
    server_name hawkeye.nineagents.in;
    location /.well-known/acme-challenge/ { root /var/www/certbot; }
    location / { return 200 "HAWKEYE provisioning - TLS pending\n"; add_header Content-Type text/plain; }
}
EOF

# 4. Enable + test + reload
ln -sfn ...
```

…ended up with the next paragraph's `# 4. Enable + test + reload` and the subsequent commands sneaking INSIDE the heredoc, before `EOF` was reached. nginx config file became invalid garbage but `nginx -t` didn't catch it because the user's terminal had already moved on.

**Root cause** — Long heredocs with surrounding markdown commentary don't survive copy-paste cleanly in some terminals. The `EOF` delimiter is generic enough that auto-completion or buffered paste can swallow it.

**Fix** — Used a unique delimiter (`NGINX_CONF_EOF`) and stripped all surrounding comments before the heredoc.

**Permanent prevention** — In all docs, when giving a heredoc:
- Use a verbose, distinct delimiter (`HAWKEYE_NGINX_EOF`, not `EOF`)
- Put the heredoc in its own fenced code block, no comments above or below inside the same block
- Tell the user to paste it standalone

---

### 10. PowerShell `curl` is an alias for `Invoke-WebRequest`, not GNU curl

**Symptom**
```powershell
> curl -I http://hawkeye.nineagents.in/

cmdlet Invoke-WebRequest at command pipeline position 1
Supply values for the following parameters:
Uri:
```
PowerShell interpreted `-I` as `-InFile` and prompted for a Uri.

**Root cause** — Built-in PowerShell alias since v3.0. Windows ships `curl.exe` (the real Microsoft-bundled GNU-style curl since Windows 10 1803), but `curl` always resolves to the alias first.

**Fix** — Use `curl.exe` explicitly: `curl.exe -I http://hawkeye.nineagents.in/`.

**Permanent prevention** — All Windows-side commands in docs now say `curl.exe …` whenever Unix-style flags are involved.

---

## Bonus: Docker Desktop kept silently dying during local builds

Out-of-scope for the prod deploy itself, but during the dev cycle Docker Desktop's WSL2 backend stalled 4-5 times, requiring "Restart Docker Desktop" from the system tray. Symptoms: API 500s on `docker ps`, builds dying with `failed to receive status: rpc error: code = Unavailable`. Root cause is Docker Desktop's WSL integration on Windows — known issue. Workaround: `Restart-Service vmcompute` or just kill+restart the Docker Desktop process. Doesn't affect prod (Linux daemon is stable).

---

## Final state — everything that's now correct on `main`

- ✅ `deploy/*.sh` and `infra/kafka/create-topics.sh` are tracked as `100755` (executable)
- ✅ `deploy.sh` does `rm -rf artifacts data` before symlinking
- ✅ `deploy.sh` hard-fails with a clear error if `/opt/hawkeye-data/` is missing models
- ✅ `deploy.sh` prints the nginx + certbot bootstrap commands inline if site config isn't installed
- ✅ Port bindings use `${BIND_HOST:-0.0.0.0}` env-var interpolation
- ✅ `docker-compose.prod.yml` is minimal — just restart policies
- ✅ `.env.example` documents `BIND_HOST` with the prod recommendation
- ✅ `DEPLOYMENT.md` has a "verify nameservers are single-vendor" step before DNS records
- ✅ `DEPLOYMENT.md` has a "test nginx with `curl --resolve`" step before certbot
- ✅ Heredocs in docs use unique delimiters and stand alone
- ✅ All Windows commands use `curl.exe` for Unix-flag compatibility

---

## Total time burned by these issues

Roughly **2.5 hours** spread across the deploy session. None of them will repeat
on the next deploy because the fixes are all merged to `main`. A clean
re-deploy from scratch on a fresh VPS following the current `DEPLOYMENT.md`
should take **30-40 minutes** end-to-end.
