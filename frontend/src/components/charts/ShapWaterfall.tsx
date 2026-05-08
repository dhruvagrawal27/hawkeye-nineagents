import { useMemo } from 'react';

interface Factor {
  name: string;
  name_human: string;
  value_human: string;
  contribution: number;
  normal: string | null;
}

/**
 * Compact horizontal waterfall: red = pushes risk up, green = pushes risk down.
 * Sorted by absolute contribution descending. Pure SVG, no D3 dependency.
 */
export function ShapWaterfall({ factors }: { factors: Factor[] }) {
  const sorted = useMemo(
    () => [...factors].sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution)),
    [factors],
  );

  if (sorted.length === 0) {
    return (
      <div className="text-sm text-slate-500 text-center py-6 italic">
        SHAP factors not yet computed for this alert.
      </div>
    );
  }

  const maxAbs = Math.max(...sorted.map((f) => Math.abs(f.contribution)), 0.01);

  return (
    <div className="space-y-1.5">
      {sorted.map((f) => {
        const pct = (Math.abs(f.contribution) / maxAbs) * 50;
        const positive = f.contribution >= 0;
        return (
          <div key={f.name} className="grid grid-cols-[12rem_1fr_3.5rem] items-center gap-2 text-xs">
            <div className="truncate" title={f.name_human}>
              <span className="text-slate-200">{f.name_human}</span>
              <span className="text-slate-500 font-mono ml-1.5">{f.value_human}</span>
            </div>
            <div className="relative h-5 bg-slate-900/40 rounded">
              <div className="absolute inset-y-0 left-1/2 w-px bg-slate-700" />
              <div
                className={
                  positive
                    ? 'absolute inset-y-0 left-1/2 bg-red-500/70 rounded-r'
                    : 'absolute inset-y-0 right-1/2 bg-emerald-500/70 rounded-l'
                }
                style={{ width: `${pct}%` }}
              />
            </div>
            <div
              className={
                positive
                  ? 'font-mono text-red-300 text-right tabular-nums'
                  : 'font-mono text-emerald-300 text-right tabular-nums'
              }
            >
              {positive ? '+' : ''}
              {f.contribution.toFixed(3)}
            </div>
          </div>
        );
      })}
    </div>
  );
}
