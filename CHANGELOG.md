# Changelog

All notable changes to HAWKEYE. Format inspired by [Keep a Changelog](https://keepachangelog.com/).

## [0.5.0] — 2026-05-09 — 🚀 Live on Hetzner

The system is now live at **<https://hawkeye.nineagents.in>**, deployed on a
Hetzner Cloud CX33 in Helsinki. Cost ~€8/month (Hetzner backups intentionally
not enabled — cost decision; can be flipped on for ~€1.60/mo extra).

### Deployment infrastructure

- **VPS**: Hetzner CX33 (4 vCPU / 8 GB / 80 GB SSD), Ubuntu 24.04, Helsinki HEL1
- **Public IP**: 204.168.183.139, DNS via Hostinger nameservers
- **TLS**: Let's Encrypt via certbot, auto-renewing through `certbot.timer`
- **Reverse proxy**: host nginx → backend:8000 (`/api`), backend:8000 (`/ws`),
  keycloak:8081 (`/auth`), frontend:8080 (`/` SPA)
- **Backend auth state**: `PREFLIGHT_MODE=1` (auth bypassed for demo —
  evaluators can browse without login). Production lockdown is one env-var
  flip away once Keycloak login is wired in the SPA.
- **CI/CD**: `git push origin main` → GitHub Actions runs `deploy.sh` over
  SSH on the VPS → docker compose up → migrate → seed → preflight → reload
  nginx. Warm deploy: ~3 min. Secrets `VPS_HOST` / `VPS_SSH_KEY` set;
  variable `DEPLOY_ENABLED=true`.

### Bugs found and fixed during the live deploy (full retro in [DEPLOYMENT_RETRO.md](DEPLOYMENT_RETRO.md))

- `deploy.sh` symlinked `/opt/hawkeye-data/artifacts → backend/artifacts`
  but compose actually binds `./artifacts`. **Fix**: switched to top-level
  symlinks; added `rm -rf` before `ln -s` so cloned-repo dirs don't trap
  the symlink inside themselves. Also added a hard-fail sanity check if
  the model artifacts aren't present after the symlink. (commit `d8c04c7`)
- `chmod +x` on `deploy/*.sh` was lost on every `git pull` because the
  Windows-authored repo tracked them as `100644`. **Fix**: changed git
  index mode to `100755`. (commit `bd2a9cd`)
- `docker-compose.prod.yml` overrode `ports:` arrays from the base file;
  Compose v2 actually MERGES port arrays instead of replacing, so
  containers tried to bind both `0.0.0.0:<port>` AND `127.0.0.1:<port>`,
  failing with EADDRINUSE. The `!reset` YAML tag made it worse (cleared
  ports entirely). **Fix**: env-var interpolation `${BIND_HOST:-0.0.0.0}`
  in the base file; prod sets `BIND_HOST=127.0.0.1`. Works on every
  compose version, no version-gated YAML tags. (commit `831f936`)

### Documentation

- `README.md` rewritten as a panel-evaluation landing page — leads with the
  live URL, explains what evaluators see in 60 seconds, surfaces the
  current `PREFLIGHT_MODE=1` state prominently.
- `DEPLOYMENT.md` got a "🟢 Currently deployed" status block at the top
  (live URL, VPS specs, cost, no-backups note, auth state, demo creds);
  the TLS section now uses the 2-step certbot webroot flow that actually
  works around the chicken-and-egg between nginx config requiring SSL
  cert files that don't exist yet.
- New `DEPLOYMENT_RETRO.md` — every gotcha we hit on the live deploy with
  the permanent fixes already in `main`. Saves ~2.5 hours on the next
  deploy.

---

## [0.4.0] — 2026-05-08 — Problem-statement alignment & insider-fraud framing

The system was always built for internal & privileged user fraud, but the UI used vague language
(“fraud detection”) that could be confused with customer fraud. This release nails the framing
verbatim from the RBI problem statement and surfaces the specific signal families it asks for.

### Added — UI

- **Mission callout** at the top of the Branch Command Center quotes the problem statement:
  *“AI-Driven Early Warning System for Internal & Privileged User Fraud”*. Lists the five signal
  families (unusual transaction patterns, off-hours access, bulk data downloads, unauthorized
  account modifications, privilege escalation attempts) and what an analyst can DO with each
  alert (risk score, SHAP, LLM memo, graph, triage).
- **`SYSTEM`** column on the live event tape — shows which banking system was touched
  (`SYS_HUB_03`, `SYS_001234`, etc.) per event.
- **`A/T`** column — Read vs Write access type (W highlighted in rose when on an alert).
- **`RECS`** column — `records_accessed` per event, highlighted amber when ≥ 50 (bulk-download).
- 📥 / 🔓 / OFF-HRS glyphs in the SIGNAL column for at-a-glance signal-family identification.

### Changed — UI

- Branch Command Center title: *“Branch Command Center · Insider Fraud”*.
- Sidebar footer: explicit *INSIDER FRAUD* tag above the NINEAGENTS / RBI NFPC line.
- User detail page header: explicit *“Bank employee · privileged-access monitoring”*
  subtitle under the user id.
- Live tape title: *“Privileged-user activity tape”* (was “Live event tape”).

### Changed — backend

- Consumer broadcasts `system_resource`, `access_type`, and `records_accessed` on every
  `event.scored` WebSocket message so the live tape can show them.

### Documentation

- README rewritten to lead with the problem statement and the signal-family table.
- This CHANGELOG file added.

---

## [0.3.0] — 2026-05-08 — Bank-Manager Command Center & multi-role

### Added

- **Three roles** (Analyst, Supervisor, Branch Manager) wired through a zustand store with
  capability flags. Role-switcher chip in the top status bar; selection persists in localStorage.
- **Branch Command Center** (`/`, lands here when role is Manager):
  - KPI strip, events/sec chart, score histogram
  - **Approval queue** — every escalated alert with one-click ✅ Approve / ❌ Reject buttons
    that fire `alertsApi.triage` with audit attribution
  - **Department rollup** table (alerts × department, with status & risk-level breakdown)
  - **7d × 24h alert heatmap** (pure SVG, no D3) — cell intensity = alerts that hour-of-day
  - **Audit feed** — scrolling list of every triage action (actor / action / alert id / time-ago)
- **Bulk-action toolbar** on the Alerts page — appears when rows are checked. Select multiple →
  Investigate / Escalate / Dismiss in one click. Per-row + select-all checkboxes are gated on
  the `canBulkAction` capability (Supervisor / Manager only).
- **Settings** page got a *Roles & Permissions* matrix table — every capability × every role
  with ✓/— marks. Click a column header to switch role from there.

### Backend

- `POST /alerts/bulk-triage` — supervisor/manager bulk action over up to 200 alert ids;
  writes one `AuditLog` entry per alert.
- `GET /alerts/queue/escalated` — alerts in `escalated` status awaiting supervisor sign-off.
- `GET /alerts/queue/mine` — alerts assigned to the current analyst.
- `GET /stats/by-department` — alerts joined to employees, grouped by department, with
  open/critical/high counts plus mean/max score and unique-employees count.
- `GET /stats/audit-log` — recent `AuditLog` entries for the audit feed.

### Backend Dockerfile

- Split into a cached deps layer (3 min, runs only on `pyproject.toml` changes) and a cheap
  source layer (~30 s, runs on every code edit). Subsequent backend rebuilds are 6× faster.

---

## [0.2.0] — 2026-05-08 — Bloomberg-terminal design pass

### Added

- **TopStatusBar** sticky across the app: live IST clock, 5 service health dots, KPI counters
  (open / 24h / high-risk / events / EPS), websocket-rate indicator.
- **EventRateChart** — 60-second sliding window of events/sec from `event.scored` WS, with
  an alerts/sec rose overlay.
- **LiveEventTicker** — stock-market-style scrolling tape, color-flashed by risk level, fed
  by `event.scored` WS messages. Embedded in Dashboard + Replay Studio.
- Custom Tailwind tokens for terminal palette (`bg`, `panel`, `line`, `ink`, `dim`, `ticker`,
  `risk.*`, `flash.*`) and font sizes `2xs` / `3xs`. Tabular numerals enabled at body level.
- 4-letter mono nav codes (DASH/ALRT/EMP/GRPH/RPLY/CFG) alongside labels in the sidebar.

### Changed

- Replay Studio: "Inject mule burst" toast confirms how many events were published.
- Score gauge (SVG arc) on the Employee detail page is now color-bound to the risk level.
- Alert cards flash on update (when score changes mid-stream).
- WebSocket handles `alert.updated` to refresh rows in place without firing a toast.

---

## [0.1.0] — 2026-05-08 — Initial scaffold

The from-scratch build. See the first commit (`3c71197`) for the long-form description.
Highlights:

- LightGBM M1+M2 blended scoring service, 146 features, threshold 0.16032509, SHAP top-5 factors.
- Groq narrative service (`openai/gpt-oss-120b`, `reasoning_effort=low`) + deterministic Jinja
  fallback so failures never reach the UI.
- Redis aggregator (base feature snapshot + live deltas), Neo4j graph upserts.
- Alert service with 60-min dedup window, broadcast on new + updated.
- Replay service: `mule_burst` mode front-loads top-mule events; auto-dismisses prior replay
  alerts on `/replay/start` so demos always show fresh activity.
- 34 backend routes, 26 unit tests passing, 10/10 preflight checks.
- Frontend scaffold: 6 pages, D3 force-directed graph, ScoreGauge, ShapWaterfall, ScoreTimeline.
- 12-service docker-compose, host nginx + certbot for `hawkeye.nineagents.in`,
  bootstrap-vps.sh + idempotent deploy.sh, GitHub Actions CI + deploy workflows.
