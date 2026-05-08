# HAWKEYE — Demo walkthrough

A 5-minute script for judges. Open the live URL, switch to the Branch Manager role, and follow
the steps. Every step has a known-good outcome.

---

## Step 0 — Open and orient (10 seconds)

Open http://localhost:8080 (or https://hawkeye.nineagents.in in production).

In the **top status bar** you should see:
- Live IST clock ticking
- All 5 service health dots green (Postgres / Redis / Neo4j / Kafka / Groq)
- KPI counters (OPEN / 24H / HIGH-RISK / EVENTS / EPS) populated
- The **role chip** at the far right showing **Branch Manager**

If a service dot is red, run `docker compose exec backend python -m app.scripts.preflight_check`
in another terminal and fix the failing service before continuing.

---

## Step 1 — Read the mission (15 seconds)

Branch Manager lands on the **Command Center** (`/`). The first thing visible is the **mission
callout** — a bordered amber/rose panel that says:

> *AI-Driven Early Warning System for Internal & Privileged User Fraud — continuously monitors
> the behaviour of internal and privileged users across banking systems… each `EMP_*` id is one
> such user.*

**What to say**:
*"HAWKEYE monitors the bank's own privileged users — staff with access to core banking, treasury,
loan origination, customer databases. Every event is one of their actions. We're not a customer
fraud system; we're the staff-side complement that watches who's misusing privilege."*

Click "got it · don't show again" so it stays out of the way for the rest of the demo.

---

## Step 2 — Browse the Command Center (45 seconds)

Read across the page:

1. **Header strip** — OPEN / ESCALATED / HIGH-RISK EMP / EVENTS counters update every 4s.
2. **Events/sec chart** — flat right now (no replay running yet); will come alive in step 4.
3. **Score distribution** — histogram of all open alerts by risk band.
4. **Approval queue** (right panel) — every escalated alert with one-click ✅ Approve / ❌ Reject.
5. **Department rollup** — alerts grouped by Core Banking / Treasury / Loans / HRMS / Compliance.
   The department with the most open alerts is at the top.
6. **7d × 24h heatmap** — alert volume as a calendar grid; off-hours and weekends light up red.
7. **Live audit feed** — every triage action with actor / action / alert id / time-ago.

**What to say**: *"This is what the Branch Manager sees. They never need to drill into individual
alerts to monitor — every cross-department signal is on one screen. They can approve escalations,
reject false positives, and see audit trails in one click."*

---

## Step 3 — Bulk triage demo (30 seconds)

Click **Alerts** in the sidebar. Notice:
- Row checkboxes on the left (only present for Manager / Supervisor roles)
- Filterable / sortable columns

Tick 3-4 rows. A blue **bulk-action toolbar** appears.

Click **Dismiss**. Toast: *"Bulk dismiss: 3 alerts updated"*. The rows fade out immediately.
Switch back to the Command Center — those alerts now show up in the Audit feed under
your username.

**What to say**: *"The Manager handles entire departments, not single alerts. Bulk actions
turn an hour-long workflow into 10 seconds. Every action is audited."*

---

## Step 4 — Live replay (90 seconds)

Click **Replay Studio** in the sidebar. Click **▶ Start mule_burst**. Toast confirms
*"Replay started — Auto-dismissed N prior replay alerts"* (so each demo is fresh).

Within 5 seconds:
- Top-bar **EPS** counter starts ticking (50-200 ev/s)
- Top-bar **WS** indicator turns green-pulsing (LIVE)
- The **Privileged-user activity tape** below the buttons starts filling with rows that
  flash green (normal) → amber (medium) → orange (high) → red (alert) and fade to neutral

Look at the tape's columns:
- **USER**: which `EMP_*` performed the action
- **SYSTEM**: which bank system was touched (`HUB_03`, `001234`, etc.)
- **A/T**: Read or **W**rite (W is rose-colored — potential unauthorized modification)
- **RECS**: records accessed (amber when ≥ 50 — bulk-download signal)
- **AMOUNT**: transaction value
- **SCORE**: the live deviation score
- **SIGNAL**: ⚠ + 📥 + 🔓 glyphs flag the signal family driving this row

Click **Inject mule burst** — within 10 seconds, 3+ red rows appear. Toast notifications
pop in the bottom-right for each new CRITICAL alert.

Switch back to **Command Center**. The events/sec chart is now alive, the approval queue
might have new entries, the audit feed scrolls.

**What to say**: *"Every row on this tape is one privileged-user action being scored against
their behavioural baseline. When the deviation crosses threshold, an alert fires — within 10
seconds of the action being authorised. The colored glyphs let an analyst spot which signal
family fired without reading the SHAP factors."*

Click **Stop**.

---

## Step 5 — Drill into one alert (45 seconds)

Click any CRITICAL alert in the live alert feed at the bottom. Slide-over opens:

- Animated **risk gauge** (SVG arc, pulses on update)
- **SHAP waterfall** — the 5 features driving this score with red/green bars
- **Investigation memo** — the Groq-generated 4-paragraph memo (`Risk Summary` / `What We Observed`
  / `Why It Matters` / `Recommended Next Step`) with the audit trail footer
- **Triage buttons** — Investigate / Escalate / Dismiss

Click "Open employee detail" — full page with:
- Big risk gauge in the header
- "Bank employee · privileged-access monitoring" subtitle (explicit framing)
- 4 tabs: **Timeline** (score history line chart), **SHAP Analysis**, **Investigation memo**,
  **Alert history**

**What to say**: *"The 'Why It Matters' paragraph in the memo is what an analyst reads first.
It cites the actual signal values verbatim. Below it, the SHAP audit trail shows the raw model
factors — meets RBI FREE-AI Guideline 5 for explainable AI."*

---

## Step 6 — Switch role to show the gating (20 seconds)

Click the **role chip** in the top status bar. Switch to **Analyst**.

Notice:
- Sidebar loses the Command Center link
- Landing page becomes the simpler Dashboard (no approval queue, no department rollup)
- On the Alerts page, row checkboxes disappear; bulk-action bar is hidden
- Slide-over still works for individual triage

Switch back to **Manager**.

**What to say**: *"Three roles, three permission tiers, capability-gated UI. In production, the
role comes from the Keycloak JWT claim `realm_access.roles` — the switcher you just used is a
demo-only override that runs when the backend is in `PREFLIGHT_MODE=1`."*

---

## Step 7 — Settings, system health, compliance (20 seconds)

Click **Settings** in the sidebar. Scroll past the Model Card (AUC 0.998, F1 0.967, threshold
0.16032509) and System Health (live, polls every 10s) to the **Roles & Permissions matrix** —
table of every capability × role with ✓/—.

Compliance footer at the bottom: *"HAWKEYE operates under a strict human-in-the-loop policy…
Compliant with RBI FREE-AI guidelines."*

**What to say**: *"This page is read-only — the model card is loaded from train_metadata.json
at backend startup, the system health is live. Compliance is built-in, not bolted-on."*

---

## If something breaks mid-demo

| Symptom | Recover |
|---|---|
| Dashboard empty | `docker compose exec backend python -m app.scripts.seed` |
| Replay button does nothing | `docker compose restart backend kafka` then re-try |
| Narrative panel hangs | Groq fallback should kick in — refresh; if still hung, `docker compose logs backend \| grep narrative` |
| Graph blank | `docker compose restart neo4j backend` and wait 20s |
| Top-bar EPS stays 0 during replay | Backend can't see Kafka — `docker compose restart backend` |

Always have `docker compose logs -f backend | grep -E 'ALERT|consumer'` in a second terminal.
