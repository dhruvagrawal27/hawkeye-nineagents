import { useQuery } from '@tanstack/react-query';
import { statsApi } from '@/lib/api';
import { useRealtimeAlerts } from '@/hooks/useRealtimeAlerts';
import { AlertCard } from '@/components/alerts/AlertCard';
import { LiveEventTicker } from '@/components/replay/LiveEventTicker';
import { Skeleton } from '@/components/ui/Skeleton';

export function Dashboard() {
  const stats = useQuery({ queryKey: ['stats', 'overview'], queryFn: statsApi.overview, refetchInterval: 5_000 });
  const dist = useQuery({ queryKey: ['stats', 'risk-distribution'], queryFn: statsApi.riskDistribution, refetchInterval: 10_000 });
  const { data: alerts = [] } = useRealtimeAlerts(20);

  return (
    <div className="space-y-6">
      {/* Stat cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Stat label="Alerts (24h)"        value={stats.data?.total_alerts_24h ?? '—'} pulse />
        <Stat label="Active high-risk"    value={stats.data?.high_risk_employees ?? '—'} />
        <Stat label="Events ingested"     value={stats.data?.events_ingested ?? '—'} />
        <Stat
          label="Detection latency"
          value={`${(stats.data?.detection_latency_ms ?? 0).toFixed(0)} ms`}
        />
      </div>

      {/* Top row: live event tape + risk distribution */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <section className="lg:col-span-2">
          <LiveEventTicker height={400} />
        </section>

        <section className="panel p-4">
          <h2 className="text-sm uppercase tracking-wider text-slate-400 mb-3">Score distribution</h2>
          <div className="flex flex-col gap-1 font-mono text-[11px]">
            {dist.isLoading ? (
              <Skeleton className="h-32 w-full" />
            ) : (
              (dist.data ?? []).map((b, i) => {
                const max = Math.max(...(dist.data ?? []).map((d) => d.count), 1);
                const width = (b.count / max) * 100;
                const isCritical = b.bin_low >= 0.85;
                const isHigh = b.bin_low >= 0.7 && !isCritical;
                const isMed = b.bin_low >= 0.5 && !isHigh && !isCritical;
                const cls = isCritical
                  ? 'bg-risk-critical/70'
                  : isHigh
                  ? 'bg-risk-high/70'
                  : isMed
                  ? 'bg-risk-medium/70'
                  : 'bg-risk-low/40';
                return (
                  <div key={i} className="flex items-center gap-2">
                    <span className="w-12 text-right text-slate-500">{b.bin_low.toFixed(2)}</span>
                    <div className="flex-1 h-3 bg-slate-800/60 rounded">
                      <div
                        className={`${cls} h-full rounded transition-all`}
                        style={{ width: `${width}%` }}
                      />
                    </div>
                    <span className="w-8 text-right text-slate-400">{b.count}</span>
                  </div>
                );
              })
            )}
          </div>
        </section>
      </div>

      {/* Bottom row: live alert feed */}
      <section className="panel p-4">
        <header className="flex items-center justify-between mb-3">
          <h2 className="text-sm uppercase tracking-wider text-slate-400">Live alert feed</h2>
          <span className="text-xs text-slate-500 font-mono">{alerts.length} shown</span>
        </header>
        {alerts.length === 0 ? (
          <div className="text-center text-slate-500 py-8 text-sm">
            Waiting for alerts… start the replay or wait for the seeded data to load.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-2">
            {alerts.slice(0, 12).map((a) => (
              <AlertCard key={a.id} alert={a} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function Stat({
  label,
  value,
  pulse,
}: {
  label: string;
  value: string | number;
  pulse?: boolean;
}) {
  return (
    <div className="stat-card">
      <span className="stat-label flex items-center gap-1.5">
        {pulse && <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />}
        {label}
      </span>
      <span className="stat-num">{value}</span>
    </div>
  );
}
