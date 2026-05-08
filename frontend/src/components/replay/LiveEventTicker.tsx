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
  system_resource?: string;
  access_type?: 'READ' | 'WRITE' | string;
  records_accessed?: number;
  receivedAt: number;
}

const MAX_TICKS = 120;
const BULK_DOWNLOAD_THRESHOLD = 50;

export function LiveEventTicker({
  height = 360,
  showAlertsOnly = false,
}: {
  height?: number;
  showAlertsOnly?: boolean;
}) {
  const [ticks, setTicks] = useState<Tick[]>([]);
  const [paused, setPaused] = useState(false);
  const [liveCount, setLiveCount] = useState(0);
  const pausedRef = useRef(paused);
  pausedRef.current = paused;

  useEffect(() => {
    hawkeyeWs.connect();
    const unsub = hawkeyeWs.subscribe((msg) => {
      if (msg.type !== 'event.scored') return;
      setLiveCount((c) => c + 1);
      if (pausedRef.current) return;
      const t = { ...(msg as any), receivedAt: Date.now() } as Tick;
      if (showAlertsOnly && !t.is_alert) return;
      setTicks((prev) => [t, ...prev].slice(0, MAX_TICKS));
    });
    return () => unsub();
  }, [showAlertsOnly]);

  return (
    <div className="panel p-0 overflow-hidden flex flex-col" style={{ height }}>
      <header className="flex items-center justify-between px-3 py-1.5 border-b border-line/60 bg-panel2/40">
        <div className="flex items-center gap-2">
          <span className={cn('h-1.5 w-1.5 rounded-full', paused ? 'bg-slate-500' : 'bg-emerald-400 animate-pulse')} />
          <span className="eyebrow">{showAlertsOnly ? 'Alert tape' : 'Privileged-user activity tape'}</span>
        </div>
        <div className="flex items-center gap-3 text-3xs font-mono text-dim tabular-nums">
          <span>{ticks.length} rows</span>
          <span>·</span>
          <span>{liveCount.toLocaleString('en-IN')} total</span>
          <button onClick={() => setPaused((p) => !p)} className="hover:text-ink transition-colors uppercase tracking-widest">
            {paused ? '▶ resume' : '⏸ pause'}
          </button>
        </div>
      </header>

      {/* Column headers */}
      <div className="grid grid-cols-[14px_14px_1fr_70px_36px_44px_72px_44px_1.5fr_56px] gap-1 px-3 py-1 border-b border-line/40 bg-panel2/30 text-3xs font-mono uppercase tracking-wider text-dim">
        <span></span>
        <span></span>
        <span>USER</span>
        <span>SYSTEM</span>
        <span title="Access type">A/T</span>
        <span className="text-right" title="Records accessed">RECS</span>
        <span className="text-right">AMOUNT ₹</span>
        <span className="text-right">SCORE</span>
        <span>SIGNAL</span>
        <span className="text-right">TIME</span>
      </div>

      <div className="flex-1 overflow-y-auto font-mono text-2xs">
        {ticks.length === 0 ? (
          <div className="text-center text-dim italic py-12 px-4 text-xs">
            Waiting for events… click ▶ Start Replay on the Replay Studio.
          </div>
        ) : (
          ticks.map((t) => <TickRow key={t.tick_id} tick={t} />)
        )}
      </div>
    </div>
  );
}

function TickRow({ tick: t }: { tick: Tick }) {
  const [fresh, setFresh] = useState(true);
  useEffect(() => {
    const id = setTimeout(() => setFresh(false), 1200);
    return () => clearTimeout(id);
  }, []);

  const color = RISK_COLOR[t.risk_level] ?? '#64748B';
  const dirIcon = t.txn_type === 'C' ? '▲' : t.txn_type === 'D' ? '▼' : '·';
  const dirColor =
    t.txn_type === 'C' ? 'text-emerald-300' :
    t.txn_type === 'D' ? 'text-rose-400'    :
                         'text-dim';
  const flashClass = t.is_alert
    ? 'bg-rose-950/50'
    : t.risk_level === 'HIGH'
    ? 'bg-orange-950/30'
    : t.risk_level === 'MEDIUM'
    ? 'bg-amber-950/20'
    : 'bg-emerald-950/10';

  const time = t.ts ? new Date(t.ts).toLocaleTimeString('en-IN', { hour12: false, timeZone: 'Asia/Kolkata' }) : '';
  const recs = t.records_accessed ?? 0;
  const isBulk = recs >= BULK_DOWNLOAD_THRESHOLD;
  const isWrite = t.access_type === 'WRITE';

  return (
    <div
      className={cn(
        'grid grid-cols-[14px_14px_1fr_70px_36px_44px_72px_44px_1.5fr_56px] gap-1 px-3 py-0.5 border-b border-line/30 transition-colors items-center',
        fresh && flashClass,
      )}
    >
      <span style={{ color }} className="text-[10px]">●</span>
      <span className={cn('leading-none', dirColor)}>{dirIcon}</span>
      <span className="truncate text-ink">{t.employee_id}</span>
      <span className="text-dim truncate uppercase" title={t.system_resource}>
        {t.system_resource ? t.system_resource.replace('SYS_', '') : '—'}
      </span>
      <span
        className={cn(
          'text-center text-[10px] font-medium uppercase',
          isWrite ? 'text-rose-300' : 'text-dim',
        )}
        title={isWrite ? 'Write access — potential unauthorized modification' : 'Read access'}
      >
        {t.access_type === 'WRITE' ? 'W' : t.access_type === 'READ' ? 'R' : '·'}
      </span>
      <span
        className={cn(
          'text-right tabular-nums',
          isBulk ? 'text-amber-300 font-medium' : 'text-dim',
        )}
        title={isBulk ? 'Bulk-download signal: 50+ records in one event' : 'Records accessed'}
      >
        {recs > 0 ? recs : '—'}
      </span>
      <span className="text-right tabular-nums text-ink">
        {Math.abs(t.amount).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
      </span>
      <span className="text-right tabular-nums" style={{ color }}>
        {t.score.toFixed(2)}
      </span>
      <span className="truncate text-dim">
        {t.is_alert && <span className="text-rose-300">⚠ </span>}
        {isBulk && <span className="text-amber-300">📥 </span>}
        {isWrite && t.is_alert && <span className="text-rose-300">🔓 </span>}
        {t.top_signal ?? ''}
        {t.is_after_hours && <span className="text-amber-400/80"> · OFF-HRS</span>}
      </span>
      <span className="text-right text-dim tabular-nums">{time}</span>
    </div>
  );
}
