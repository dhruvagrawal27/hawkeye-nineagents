import { useState } from 'react';
import { ChevronDown, ChevronUp, ShieldAlert } from 'lucide-react';
import { cn } from '@/lib/format';

/**
 * Verbatim problem-statement framing — so a panel reading the dashboard
 * cold can answer "what is this thing?" in 10 seconds without asking us.
 */
export function MissionCallout() {
  const [open, setOpen] = useState(() => {
    return localStorage.getItem('hawkeye:mission-seen-v2') !== '1';
  });

  const dismiss = () => {
    setOpen(false);
    localStorage.setItem('hawkeye:mission-seen-v2', '1');
  };

  return (
    <section className={cn(
      'panel-paper overflow-hidden',
      open ? 'p-4' : 'px-4 py-2',
    )}>
      <header
        onClick={() => setOpen((p) => !p)}
        className="flex items-center gap-3 cursor-pointer select-none"
      >
        <ShieldAlert size={open ? 18 : 14} className="text-amber-400 shrink-0" />
        <div className="flex-1">
          <h2 className={cn('font-semibold tracking-wide text-ink', open ? 'text-base' : 'text-xs')}>
            AI-Driven Early Warning System for Internal &amp; Privileged User Fraud
          </h2>
          {!open && (
            <span className="text-2xs font-mono text-dim uppercase tracking-widest">
              Behavioural baselines · privilege-misuse signals · click to expand
            </span>
          )}
        </div>
        {open ? <ChevronUp size={14} className="text-dim" /> : <ChevronDown size={14} className="text-dim" />}
      </header>

      {open && (
        <div className="mt-3 space-y-3 text-xs leading-relaxed">
          <p className="text-slate-200">
            HAWKEYE continuously monitors the behaviour of <strong className="text-ink">internal and privileged
            users</strong> across banking systems — core banking, treasury, loan origination, customer
            databases — and flags anomalous or potentially fraudulent activities in real time. Each
            <code className="font-mono text-amber-300 mx-1">EMP_*</code> id on the dashboard is one such
            user; their LightGBM-blended risk score is the live deviation from their behavioural baseline.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <Box title="What we monitor — behavioural baselines">
              <ul className="space-y-1.5 list-none">
                <li><Tag>UNUSUAL TXN PATTERNS</Tag> — pass-through %, structuring at ₹45-49K, fan-out velocity</li>
                <li><Tag>OFF-HOURS ACCESS</Tag> — fraction of activity 22:00-06:00 IST, weekend access</li>
                <li><Tag>BULK DATA DOWNLOADS</Tag> — high <code className="font-mono">records_accessed</code> on customer-DB reads</li>
                <li><Tag>UNAUTH ACCT MODS</Tag> — WRITE to systems outside the user's role / branch</li>
                <li><Tag>PRIV ESCALATION</Tag> — access pattern fanning to systems not previously touched</li>
              </ul>
            </Box>
            <Box title="What you can DO with the alert">
              <ul className="space-y-1.5 list-none">
                <li><Tag tone="ok">RISK SCORE</Tag> — 0-1 with risk-band (LOW / MEDIUM / HIGH / CRITICAL)</li>
                <li><Tag tone="ok">SHAP EXPLANATION</Tag> — the 5 features driving this score, in plain English</li>
                <li><Tag tone="ok">LLM NARRATIVE</Tag> — Groq-generated investigation memo with audit footer</li>
                <li><Tag tone="ok">GRAPH NEIGHBOURHOOD</Tag> — shared systems with other flagged users</li>
                <li><Tag tone="ok">TRIAGE WORKFLOW</Tag> — assign / escalate / dismiss with audit trail</li>
              </ul>
            </Box>
          </div>

          <p className="text-2xs text-dim italic pt-2 border-t border-line/40">
            HAWKEYE is the staff-side complement to the bank's customer-fraud stack
            (UPI / AePS / FRMS). Customer transactions are not the unit of monitoring here —
            <span className="text-ink"> the privileged user behind the action is</span>.
          </p>

          <div className="flex justify-end">
            <button
              onClick={dismiss}
              className="text-2xs font-mono uppercase tracking-widest text-dim hover:text-ink transition-colors"
            >
              Got it · don't show again
            </button>
          </div>
        </div>
      )}
    </section>
  );
}

function Box({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded border border-line/40 bg-panel2/40 p-3">
      <div className="text-3xs font-mono uppercase tracking-widest mb-2 text-amber-300/90">{title}</div>
      <div className="text-slate-200 text-2xs leading-relaxed">{children}</div>
    </div>
  );
}

function Tag({ children, tone }: { children: React.ReactNode; tone?: 'ok' }) {
  const cls =
    tone === 'ok'
      ? 'bg-emerald-900/40 text-emerald-300 border-emerald-900/60'
      : 'bg-rose-900/30 text-rose-200 border-rose-900/60';
  return (
    <span className={cn('inline-block px-1.5 py-0.5 rounded border text-3xs font-mono uppercase tracking-widest mr-1.5', cls)}>
      {children}
    </span>
  );
}
