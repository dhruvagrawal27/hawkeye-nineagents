import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import { employeesApi, statsApi } from '@/lib/api';
import { useRealtimeAlerts } from '@/hooks/useRealtimeAlerts';
import { LiveEventTicker } from '@/components/replay/LiveEventTicker';
import { EventRateChart } from '@/components/charts/EventRateChart';
import { RiskBadge } from '@/components/ui/RiskBadge';
import { Skeleton } from '@/components/ui/Skeleton';
import { cn, timeAgo } from '@/lib/format';

export function Dashboard() {
  const stats = useQuery({ queryKey: ['stats', 'overview'], queryFn: statsApi.overview, refetchInterval: 4_000 });
  const dist = useQuery({ queryKey: ['stats', 'risk-distribution'], queryFn: statsApi.riskDistribution, refetchInterval: 8_000 });
  const top = useQuery({ queryKey: ['employees', 'top-dash'], queryFn: () => employeesApi.top(10), refetchInterval: 8_000 });
  const { data: alerts = [] } = useRealtimeAlerts(40);

  return (
    <div className="space-y-3">
      {/* L0 stat strip */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat label="OPEN ALERTS"     value={stats.data?.alerts_open}        accent />
        <Stat label="ALERTS · 24H"    value={stats.data?.total_alerts_24h} />
        <Stat label="HIGH-RISK EMP."  value={stats.data?.high_risk_employees} />
        <Stat label="DETECT LATENCY"  value={`${(stats.data?.detection_latency_ms ?? 0).toFixed(0)} ms`} />
      </div>

      {/* L1 row: rate chart + score distribution */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-3">
        <div className="xl:col-span-2">
          <EventRateChart height={120} />
        </div>
        <RiskHistogram dist={dist.data ?? []} loading={dist.isLoading} />
      </div>

      {/* L2 row: live tape + top movers */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-3">
        <div className="xl:col-span-2">
          <LiveEventTicker height={460} />
        </div>
        <TopMovers top={top.data ?? []} loading={top.isLoading} />
      </div>

      {/* L3: live alert feed (compact list) */}
      <section className="panel p-0 overflow-hidden">
        <header className="flex items-center justify-between px-4 py-2 border-b border-line/60">
          <span className="eyebrow flex items-center gap-2">
            <span className="live-dot" /> Live alert tape
          </span>
          <span className="text-2xs font-mono text-dim">{alerts.length} most recent</span>
        </header>
        {alerts.length === 0 ? (
          <div className="text-center text-dim py-6 text-sm">No alerts yet — start replay to see activity.</div>
        ) : (
          <table className="w-full text-2xs font-mono">
            <thead>
              <tr className="bg-panel2/50 text-dim border-b border-line/60">
                <th className="text-left px-3 py-1.5 w-20">RISK</th>
                <th className="text-left px-3 py-1.5 w-32">EMPLOYEE</th>
                <th className="text-right px-3 py-1.5 w-16">SCORE</th>
                <th className="text-left px-3 py-1.5">SIGNAL</th>
                <th className="text-left px-3 py-1.5 w-20">SOURCE</th>
                <th className="text-right px-3 py-1.5 w-24">TRIGGERED</th>
              </tr>
            </thead>
            <tbody>
              {alerts.slice(0, 14).map((a) => (
                <tr key={a.id} className="border-b border-line/30 row-hover">
                  <td className="px-3 py-1"><RiskBadge level={a.risk_level} /></td>
                  <td className="px-3 py-1 text-ink">{a.employee_id}</td>
                  <td className="px-3 py-1 text-right tabular-nums text-ink">{a.display_score.toFixed(2)}</td>
                  <td className="px-3 py-1 text-dim truncate max-w-md">{a.top_signal ?? '—'}</td>
                  <td className="px-3 py-1 text-dim uppercase">{a.source}</td>
                  <td className="px-3 py-1 text-right text-dim">{timeAgo(a.triggered_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <footer className="px-4 py-2 border-t border-line/60 flex items-center justify-end">
          <Link to="/alerts" className="text-2xs font-mono uppercase tracking-widest text-accent hover:text-accent2 inline-flex items-center gap-1">
            All alerts <ArrowRight size={11} />
          </Link>
        </footer>
      </section>
    </div>
  );
}

function Stat({
  label,
  value,
  accent,
}: {
  label: string;
  value: string | number | undefined;
  accent?: boolean;
}) {
  const display = value === undefined ? '—' : typeof value === 'number' ? value.toLocaleString('en-IN') : value;
  return (
    <div className="stat-card">
      <span className="stat-label">{label}</span>
      <span className={cn('stat-num', accent && 'text-accent')}>{display}</span>
    </div>
  );
}

function RiskHistogram({ dist, loading }: { dist: { bin_low: number; bin_high: number; count: number }[]; loading: boolean }) {
  const max = Math.max(...dist.map((d) => d.count), 1);
  return (
    <div className="panel p-3">
      <span className="eyebrow">Score distribution</span>
      <div className="mt-2 flex flex-col gap-0.5 font-mono text-2xs">
        {loading ? (
          <Skeleton className="h-32 w-full" />
        ) : dist.length === 0 ? (
          <span className="text-dim italic">No data</span>
        ) : (
          dist.map((b, i) => {
            const w = (b.count / max) * 100;
            const cls =
              b.bin_low >= 0.85 ? 'bg-risk-critical/70' :
              b.bin_low >= 0.7  ? 'bg-risk-high/70'     :
              b.bin_low >= 0.5  ? 'bg-risk-medium/70'   :
                                  'bg-risk-low/40';
            return (
              <div key={i} className="flex items-center gap-2 leading-none">
                <span className="w-9 text-right tabular-nums text-dim">{b.bin_low.toFixed(2)}</span>
                <div className="flex-1 h-2 bg-line/40 rounded-sm overflow-hidden">
                  <div className={cn(cls, 'h-full transition-all')} style={{ width: `${w}%` }} />
                </div>
                <span className="w-7 text-right tabular-nums text-ink">{b.count}</span>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

function TopMovers({ top, loading }: { top: any[]; loading: boolean }) {
  return (
    <div className="panel p-0 overflow-hidden">
      <header className="flex items-center justify-between px-3 py-1.5 border-b border-line/60">
        <span className="eyebrow">Top risk · live</span>
        <Link to="/employees" className="text-2xs font-mono uppercase tracking-widest text-accent hover:text-accent2">
          all →
        </Link>
      </header>
      {loading ? (
        <div className="p-3"><Skeleton className="h-32" /></div>
      ) : top.length === 0 ? (
        <div className="p-4 text-dim text-sm italic text-center">No high-risk employees yet.</div>
      ) : (
        <table className="w-full text-2xs font-mono">
          <thead>
            <tr className="bg-panel2/40 text-dim border-b border-line/60">
              <th className="text-left  px-3 py-1.5 w-6">#</th>
              <th className="text-left  px-3 py-1.5">EMPLOYEE</th>
              <th className="text-right px-3 py-1.5 w-14">SCORE</th>
              <th className="text-right px-3 py-1.5 w-12">ALERTS</th>
            </tr>
          </thead>
          <tbody>
            {top.map((e, i) => (
              <tr key={e.id} className="border-b border-line/30 row-hover">
                <td className="px-3 py-1 text-dim">{i + 1}</td>
                <td className="px-3 py-1">
                  <Link to={`/employees/${e.id}`} className="text-ink hover:text-accent">
                    {e.id}
                  </Link>
                  <div className="text-dim text-3xs">{e.department}</div>
                </td>
                <td className="px-3 py-1 text-right tabular-nums" style={{ color: '#F43F5E' }}>
                  {e.display_score?.toFixed(2) ?? '—'}
                </td>
                <td className="px-3 py-1 text-right tabular-nums text-ink">{e.open_alert_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
