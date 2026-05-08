import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Activity } from 'lucide-react';
import { settingsApi, statsApi } from '@/lib/api';
import { hawkeyeWs } from '@/lib/ws';
import { cn } from '@/lib/format';
import { RoleSwitcher } from '@/components/layout/RoleSwitcher';

/**
 * Persistent across-the-top status strip — Bloomberg-style L0 bar.
 * Shows live wall clock (IST), service health dots, key counters,
 * websocket connectivity, and the live event-rate badge.
 */
export function TopStatusBar() {
  const [now, setNow] = useState(() => new Date());
  const [wsActive, setWsActive] = useState(false);
  const [recentTicks, setRecentTicks] = useState<number[]>([]);

  const ready = useQuery({
    queryKey: ['readyz', 'topbar'],
    queryFn: settingsApi.ready,
    refetchInterval: 8_000,
  });
  const stats = useQuery({
    queryKey: ['stats', 'overview', 'topbar'],
    queryFn: statsApi.overview,
    refetchInterval: 4_000,
  });

  // Wall clock
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1_000);
    return () => clearInterval(id);
  }, []);

  // Track WS rate
  useEffect(() => {
    hawkeyeWs.connect();
    const unsub = hawkeyeWs.subscribe((msg) => {
      if (msg.type === 'event.scored') {
        setWsActive(true);
        setRecentTicks((prev) => [...prev.slice(-29), Date.now()]);
      }
    });
    const id = setInterval(() => {
      // Drop ticks older than 10s; if none recent, mark inactive
      const cutoff = Date.now() - 10_000;
      setRecentTicks((prev) => prev.filter((t) => t > cutoff));
      setWsActive((active) => (recentTicks.length > 0 ? active : false));
    }, 1_000);
    return () => {
      unsub();
      clearInterval(id);
    };
  }, [recentTicks.length]);

  const eps = recentTicks.length > 1
    ? Math.round(recentTicks.length / Math.max(1, (Date.now() - recentTicks[0]) / 1000))
    : 0;

  const services = ready.data?.services ?? {};
  const allOk = Object.values(services).every((s: any) => s.status === 'ok');

  return (
    <div className="bg-bg/95 backdrop-blur border-b border-line/80 px-4 py-1.5 flex items-center gap-4 text-2xs font-mono uppercase tracking-wider text-dim sticky top-0 z-30">
      {/* Brand */}
      <div className="flex items-center gap-2">
        <Activity size={12} className="text-accent" />
        <span className="text-ink font-semibold tracking-[0.22em]">HAWKEYE</span>
        <span className="text-dim">v0.1</span>
      </div>

      <Separator />

      {/* Wall clock */}
      <span className="tabular-nums text-ink">
        {now.toLocaleTimeString('en-IN', { hour12: false, timeZone: 'Asia/Kolkata' })} IST
      </span>
      <span className="text-dim/60">·</span>
      <span className="tabular-nums">
        {now.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', timeZone: 'Asia/Kolkata' }).toUpperCase()}
      </span>

      <Separator />

      {/* Service health dots */}
      <div className="flex items-center gap-1.5">
        <span className={cn('eyebrow', allOk ? 'text-emerald-300' : 'text-amber-300')}>
          SVCS
        </span>
        {Object.entries(services).map(([name, svc]: any) => (
          <ServiceDot key={name} name={name} status={svc.status} />
        ))}
      </div>

      <Separator />

      {/* KPIs */}
      <KPI label="ALERTS-24H" value={stats.data?.total_alerts_24h ?? '—'} />
      <KPI label="HIGH-RISK"  value={stats.data?.high_risk_employees ?? '—'} />
      <KPI label="EVENTS"     value={stats.data?.events_ingested ?? 0} />
      <KPI label="EPS"        value={eps} highlight />

      <div className="flex-1" />

      {/* WS status */}
      <div className="flex items-center gap-1.5">
        <span className={cn('h-1.5 w-1.5 rounded-full', wsActive ? 'bg-emerald-400 animate-pulse' : 'bg-slate-600')} />
        <span className="tabular-nums">{wsActive ? 'WS · LIVE' : 'WS · IDLE'}</span>
      </div>

      <Separator />

      <RoleSwitcher />
    </div>
  );
}

function Separator() {
  return <span className="h-3 w-px bg-line/80" />;
}

function ServiceDot({ name, status }: { name: string; status: string }) {
  const color =
    status === 'ok'   ? 'bg-emerald-400 shadow-[0_0_4px] shadow-emerald-400/70' :
    status === 'down' ? 'bg-red-500   shadow-[0_0_4px] shadow-red-500/70'    :
                        'bg-amber-400 shadow-[0_0_4px] shadow-amber-400/70';
  return (
    <span title={`${name}: ${status}`} className={cn('h-1.5 w-1.5 rounded-full', color)} />
  );
}

function KPI({ label, value, highlight }: { label: string; value: string | number; highlight?: boolean }) {
  return (
    <div className="flex items-baseline gap-1.5">
      <span className="text-dim">{label}</span>
      <span
        key={String(value)}
        className={cn(
          'text-ink tabular-nums font-medium',
          highlight && Number(value) > 0 && 'text-ticker',
        )}
      >
        {value}
      </span>
    </div>
  );
}
