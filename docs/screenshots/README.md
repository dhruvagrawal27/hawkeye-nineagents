# HAWKEYE — Screenshots for the README

This directory holds the dashboard screenshots embedded in the main
[README.md](../../README.md). All filenames listed below are referenced from
the README — capture each at the prescribed resolution and drop into this
folder.

## Capture procedure

1. Open <https://hawkeye.nineagents.in> in **Chrome** at full-window 1440×900
   (Cmd/Ctrl+0 to ensure 100% zoom).
2. Wait for the page to fully load (top-bar IST clock ticking, all 5 service
   dots green).
3. Use the OS screenshot tool:
   - Windows: `Win+Shift+S` → window/region → save as PNG
   - macOS: `Cmd+Shift+5` → window or region → save as PNG
4. Save into this folder with the exact filenames below.
5. Optimise PNGs with `pngquant --quality=80-95 *.png` to keep repo size sane.

## Required screenshots

| Filename | URL to capture | What to show |
|---|---|---|
| `01-command-center-hero.png` | `/` (after Mission Callout dismissed) | Branch Manager Command Center: top stat strip + events/sec chart + score histogram + approval queue + dept rollup + heatmap visible. The "money shot" for the README hero. |
| `02-mission-callout.png` | `/` (Mission Callout expanded) | Just the amber Mission Callout panel. Crops nicely; explains "what HAWKEYE actually monitors" in one image. |
| `03-live-event-tape.png` | `/replay` (after starting mule_burst replay) | The live event tape mid-flow — multiple coloured rows visible, ideally with at least one ⚠ alert and one 📥 bulk-download flag. |
| `04-employee-detail-shap.png` | `/employees/<any CRITICAL employee id>` → SHAP Analysis tab | The SHAP waterfall chart with red+green bars, plus the score gauge at top. |
| `05-narrative-memo.png` | `/employees/<id>` → Investigation memo tab | The Groq-generated 4-paragraph memo with the audit trail footer. Shows the dual-audience writing. |
| `06-graph-explorer-clusters.png` | `/graph` with "Cluster by dept" toggled ON | Force-directed graph with 5 dept clusters arranged in a pentagon, dashed circles labeled CORE BANKING / TREASURY / etc. |
| `07-alerts-bulk-action.png` | `/alerts` with 3-4 rows checked | Alerts table with the blue bulk-action toolbar visible (Investigate / Escalate / Dismiss / Clear buttons). Demonstrates the supervisor/manager workflow. |
| `08-settings-roles-matrix.png` | `/settings` scrolled to Roles & Permissions | The capabilities-by-role matrix with ✓ / — marks. Shows the role-based access control story. |

## Optional — extra captures that look good

| Filename | What to show |
|---|---|
| `09-replay-studio-controls.png` | Replay Studio with the three big buttons (▶ Start / Stop / Inject burst) + live counters ticking |
| `10-toast-notification.png` | Right-bottom corner just after a CRITICAL alert fires (red animated toast visible) |
| `11-mobile-dashboard.png` | Same as `01` but at 375×812 (iPhone) to show responsive layout |

## After capturing

The README already has `<img>` tags pointing at these paths. As soon as the
files land in this folder and you `git add docs/screenshots/*.png`, they'll
render on GitHub.

Quick sanity check before committing:

```bash
ls -la docs/screenshots/*.png
# Each file should be 200 KB - 1 MB after pngquant
```

> ℹ️ **Public repo note**: these screenshots are public. Verify each one
> doesn't accidentally show real personal info (your real Groq API key in
> a tooltip, real email addresses, etc.). The current production data is
> all synthetic so this should be a non-issue, but worth a glance.
