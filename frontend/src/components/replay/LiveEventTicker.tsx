import { useEffect, useRef, useState } from 'react';
import { hawkeyeWs } from '@/lib/ws';
import { cn, RISK_COLOR } from '@/lib/format';

interface Tick {
  tick_id: number;
  employee_id: string;
  account_id: string;
  score: number;
  raw_score: number;
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  is_alert: boolean;
  top_signal: string | null;
  amount: number;
  txn_type: string;
  channel: string;
  is_after_hours: boolean;
  ts: string;
  receivedAt: number;
}

const MAX_TICKS = 80;

export function LiveEventTicker({
  height = 360,
  showAlertsOnly = false,
}: {
  height?: number;
  showAlertsOnly?: boolean;
}) {
  const [ticks, setTicks] = useState<Tick[]>([]);
  const [paused, setPaused] = useState(false);
  const pausedRef = useRef(paused);
  pausedRef.current = paused;

  useEffect(() => {
    hawkeyeWs.connect();
    const unsub = hawkeyeWs.subscribe((msg) => {
      if (pausedRef.current) return;
      if (msg.type === 'event.scored') {
        const t = { ...(msg as any), receivedAt: Date.now() } as Tick;
        if (showAlertsOnly && !t.is_alert) return;
        setTicks((prev) => [t, ...prev].slice(0, MAX_TICKS));
      }
    });
    return () => unsub();
  }, [showAlertsOnly]);

  return (
    <div className="panel overflow-hidden flex flex-col" style={{ height }}>
      <header className="flex items-center justify-between px-4 py-2 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <span className={cn('h-2 w-2 rounded-full', paused ? 'bg-slate-500' : 'bg-emerald-400 animate-pulse')} />
          <h3 className="text-xs uppercase tracking-widest text-slate-400">
            {showAlertsOnly ? 'Live alert tape' : 'Live event tape'}
          </h3>
        </div>
        <div className="flex items-center gap-2 text-[10px] font-mono text-slate-500">
          <span>{ticks.length}</span>
          <button
            onClick={() => setPaused((p) => !p)}
            className="text-slate-500 hover:text-slate-200 transition-colors"
          >
            {paused ? 'resume' : 'pause'}
          </button>
        </div>
      </header>
      <div className="flex-1 overflow-y-auto font-mono text-[11px]">
        {ticks.length === 0 ? (
          <div className="text-center text-slate-500 italic mt-8 px-4">
            Start replay to see events flowing in real-time…
          </div>
        ) : (
          <table className="w-full">
            <tbody>
              {ticks.map((t) => (
                <TickRow key={t.tick_id} tick={t} />
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function TickRow({ tick: t }: { tick: Tick }) {
  // Briefly highlight on insert — fade out over 1.2s
  const [fresh, setFresh] = useState(true);
  useEffect(() => {
    const id = setTimeout(() => setFresh(false), 1200);
    return () => clearTimeout(id);
  }, []);

  const color = RISK_COLOR[t.risk_level] ?? '#64748b';
  const dirIcon = t.txn_type === 'C' ? '▲' : t.txn_type === 'D' ? '▼' : '·';
  const dirColor = t.txn_type === 'C' ? 'text-emerald-300' : t.txn_type === 'D' ? 'text-red-300' : 'text-slate-500';
  const flashClass = t.is_alert
    ? 'bg-red-900/40'
    : t.risk_level === 'HIGH'
    ? 'bg-orange-900/30'
    : t.risk_level === 'MEDIUM'
    ? 'bg-amber-900/20'
    : 'bg-emerald-900/15';

  return (
    <tr
      className={cn(
        'border-b border-slate-800/40 transition-colors',
        fresh && flashClass,
      )}
    >
      <td className="py-1 pl-3 pr-1 w-3" style={{ color }}>
        ●
      </td>
      <td className={cn('py-1 px-1 w-3', dirColor)}>{dirIcon}</td>
      <td className="py-1 px-1 w-32 truncate text-slate-300">{t.employee_id}</td>
      <td className="py-1 px-1 w-16 text-slate-500">{t.channel}</td>
      <td className="py-1 px-1 w-20 text-right tabular-nums text-slate-300">
        {Math.abs(t.amount).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
      </td>
      <td className="py-1 px-1 w-12 text-right tabular-nums" style={{ color }}>
        {t.score.toFixed(2)}
      </td>
      <td className="py-1 pr-3 pl-1 truncate text-slate-400">
        {t.is_alert ? '⚠ ' : ''}
        {t.top_signal ?? ''}
        {t.is_after_hours && <span className="text-slate-500"> · off-hrs</span>}
      </td>
    </tr>
  );
}
