import { Network, Sparkles, GitBranch, AlertTriangle } from 'lucide-react';
import type { Alert } from '@/lib/api';

const FUSION_WEIGHTS = { lgb: 0.88, thgnn: 0.08, simclr: 0.04 };
const THRESHOLD = 0.16032509;

/**
 * Visual breakdown of how the fused score was computed.
 * Shows each model's raw probability, its weight in the blend, and the
 * resulting fused score. If the LightGBM-only score would have been below
 * the alert threshold but the fused score crossed it, surfaces a "rescued
 * by graph fusion" badge — the canonical pitch story for the GNN signal.
 */
export function ScoreComposition({ alert }: { alert: Alert }) {
  // Backwards-compat: alerts created before fusion shipped have null components.
  if (alert.lgb_blend == null) {
    return (
      <div className="text-xs text-slate-500 font-mono">
        Raw blend {alert.score.toFixed(4)} · Threshold {THRESHOLD.toFixed(4)}
        <span className="ml-2 text-slate-600">(legacy alert · no fusion data)</span>
      </div>
    );
  }

  const lgb = alert.lgb_blend;
  const thgnn = alert.thgnn_proba;
  const simclr = alert.simclr_proba;

  // The "would LightGBM alone have caught this?" check.
  const wouldHaveBeenMissed = lgb < THRESHOLD && alert.score >= THRESHOLD;

  const rows: Array<{
    icon: JSX.Element;
    label: string;
    sublabel: string;
    value: number | null | undefined;
    weight: number;
    barColor: string;
  }> = [
    {
      icon: <GitBranch size={12} className="text-slate-300" />,
      label: 'LightGBM blend',
      sublabel: 'M1+M2 supervised — 105/146 features',
      value: lgb,
      weight: FUSION_WEIGHTS.lgb,
      barColor: 'bg-slate-400',
    },
    {
      icon: <Network size={12} className="text-violet-300" />,
      label: 'T-HGNN graph signal',
      sublabel: '2-layer HGT — account ↔ counterparty',
      value: thgnn,
      weight: FUSION_WEIGHTS.thgnn,
      barColor: 'bg-violet-400',
    },
    {
      icon: <Sparkles size={12} className="text-cyan-300" />,
      label: 'SimCLR cold-start',
      sublabel: 'Self-supervised contrastive embedding',
      value: simclr,
      weight: FUSION_WEIGHTS.simclr,
      barColor: 'bg-cyan-400',
    },
  ];

  return (
    <div className="space-y-3">
      <header className="flex items-center justify-between">
        <h3 className="text-xs uppercase tracking-widest text-slate-400">Score composition</h3>
        <span className="text-2xs text-slate-500 font-mono">
          fused = {alert.score.toFixed(4)} · threshold {THRESHOLD.toFixed(4)}
        </span>
      </header>

      <div className="rounded-lg border border-slate-800 bg-slate-900/40 divide-y divide-slate-800">
        {rows.map((r) => {
          const present = r.value != null;
          const pct = present ? Math.max(0, Math.min(1, r.value!)) * 100 : 0;
          const contribution = present ? r.value! * r.weight : 0;
          return (
            <div key={r.label} className="px-3 py-2">
              <div className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-2 min-w-0">
                  {r.icon}
                  <div className="min-w-0">
                    <div className="text-slate-200 truncate">
                      {r.label}{' '}
                      <span className="text-slate-500 font-mono text-2xs">
                        ×{(r.weight * 100).toFixed(0)}%
                      </span>
                    </div>
                    <div className="text-2xs text-slate-500 truncate">{r.sublabel}</div>
                  </div>
                </div>
                <div className="text-right font-mono shrink-0 ml-3">
                  {present ? (
                    <>
                      <div className="text-slate-200">{r.value!.toFixed(4)}</div>
                      <div className="text-2xs text-slate-500">
                        contrib {contribution >= 0 ? '+' : ''}
                        {contribution.toFixed(4)}
                      </div>
                    </>
                  ) : (
                    <div className="text-slate-600 italic text-2xs">not loaded</div>
                  )}
                </div>
              </div>
              <div className="h-1 mt-1.5 bg-slate-800 rounded overflow-hidden">
                <div
                  className={`h-full ${r.barColor} transition-all`}
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>

      {wouldHaveBeenMissed && (
        <div className="rounded-lg border border-amber-700/60 bg-amber-900/20 px-3 py-2">
          <div className="flex items-start gap-2">
            <AlertTriangle size={14} className="text-amber-400 mt-0.5 shrink-0" />
            <div className="text-xs space-y-1">
              <div className="text-amber-200 font-medium">Rescued by graph fusion</div>
              <div className="text-amber-100/80 leading-relaxed">
                LightGBM alone scored this account at{' '}
                <span className="font-mono">{lgb.toFixed(4)}</span> — below the{' '}
                <span className="font-mono">{THRESHOLD.toFixed(4)}</span> alert threshold.
                T-HGNN graph propagation (
                {thgnn != null ? thgnn.toFixed(2) : '—'}) and SimCLR cold-start (
                {simclr != null ? simclr.toFixed(2) : '—'}) lifted the fused score
                to <span className="font-mono">{alert.score.toFixed(4)}</span>, crossing the threshold.
                Without graph fusion, this alert would not have fired.
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
