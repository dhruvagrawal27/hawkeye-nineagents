import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ArrowDown, ArrowUp, Search } from 'lucide-react';
import type { Alert } from '@/lib/api';
import { alertsApi } from '@/lib/api';
import { useRealtimeAlerts } from '@/hooks/useRealtimeAlerts';
import { RiskBadge } from '@/components/ui/RiskBadge';
import { Skeleton } from '@/components/ui/Skeleton';
import { AlertSlideOver } from '@/components/alerts/AlertSlideOver';
import { cn, timeAgo } from '@/lib/format';

type SortKey = 'triggered_at' | 'score' | 'risk_level' | 'employee_id';

const RISK_RANK: Record<string, number> = { CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1 };

export function AlertsPage() {
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [riskFilter, setRiskFilter] = useState<string>('all');
  const [search, setSearch] = useState('');
  const [sortKey, setSortKey] = useState<SortKey>('triggered_at');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const [selected, setSelected] = useState<Alert | null>(null);

  // Live updates from WebSocket so the table stays fresh
  useRealtimeAlerts(200);

  const query = useQuery({
    queryKey: ['alerts', { limit: 200, statusFilter, riskFilter }],
    queryFn: () =>
      alertsApi.list({
        limit: 200,
        status: statusFilter === 'all' ? undefined : statusFilter,
        risk_level: riskFilter === 'all' ? undefined : riskFilter,
      }),
    refetchInterval: 15_000,
  });

  const filtered = useMemo(() => {
    let rows = query.data ?? [];
    if (search.trim()) {
      const q = search.toLowerCase();
      rows = rows.filter(
        (r) => r.employee_id.toLowerCase().includes(q) || r.account_id.toLowerCase().includes(q),
      );
    }
    rows = [...rows].sort((a, b) => {
      let cmp = 0;
      if (sortKey === 'triggered_at') {
        cmp = new Date(a.triggered_at).getTime() - new Date(b.triggered_at).getTime();
      } else if (sortKey === 'score') {
        cmp = a.display_score - b.display_score;
      } else if (sortKey === 'risk_level') {
        cmp = (RISK_RANK[a.risk_level] ?? 0) - (RISK_RANK[b.risk_level] ?? 0);
      } else if (sortKey === 'employee_id') {
        cmp = a.employee_id.localeCompare(b.employee_id);
      }
      return sortDir === 'asc' ? cmp : -cmp;
    });
    return rows;
  }, [query.data, search, sortKey, sortDir]);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key);
      setSortDir('desc');
    }
  };

  return (
    <div className="space-y-6">
      <header className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-semibold text-slate-100">Alerts</h1>
          <p className="text-sm text-slate-400 mt-1">
            {filtered.length} of {query.data?.length ?? 0} alerts
          </p>
        </div>
        <div className="flex gap-2 flex-wrap">
          <SegmentedControl
            value={statusFilter}
            onChange={setStatusFilter}
            options={[
              { value: 'all', label: 'All' },
              { value: 'open', label: 'Open' },
              { value: 'investigating', label: 'Investigating' },
              { value: 'escalated', label: 'Escalated' },
              { value: 'dismissed', label: 'Dismissed' },
            ]}
          />
          <SegmentedControl
            value={riskFilter}
            onChange={setRiskFilter}
            options={[
              { value: 'all', label: 'All risk' },
              { value: 'CRITICAL', label: 'Critical' },
              { value: 'HIGH', label: 'High' },
              { value: 'MEDIUM', label: 'Medium' },
            ]}
          />
        </div>
      </header>

      <div className="panel p-4">
        <div className="relative mb-3">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by employee or account ID…"
            className="w-full bg-slate-900/50 border border-slate-800 rounded-lg pl-9 pr-3 py-2 text-sm placeholder-slate-500 focus:outline-none focus:border-accent transition-colors"
          />
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs uppercase tracking-wider text-slate-500 border-b border-slate-800">
                <SortHeader label="Risk" k="risk_level" sortKey={sortKey} sortDir={sortDir} onClick={toggleSort} className="w-24" />
                <SortHeader label="Employee" k="employee_id" sortKey={sortKey} sortDir={sortDir} onClick={toggleSort} />
                <th className="text-left py-2 px-2">Top signal</th>
                <SortHeader label="Score" k="score" sortKey={sortKey} sortDir={sortDir} onClick={toggleSort} className="w-20 text-right" align="right" />
                <th className="text-left py-2 px-2 w-28">Status</th>
                <SortHeader label="Triggered" k="triggered_at" sortKey={sortKey} sortDir={sortDir} onClick={toggleSort} className="w-32" />
              </tr>
            </thead>
            <tbody>
              {query.isLoading ? (
                Array.from({ length: 8 }).map((_, i) => (
                  <tr key={i}>
                    <td colSpan={6} className="py-1.5">
                      <Skeleton className="h-9 w-full" />
                    </td>
                  </tr>
                ))
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan={6} className="text-center py-10 text-slate-500 text-sm italic">
                    No alerts match the current filters.
                  </td>
                </tr>
              ) : (
                filtered.map((a) => (
                  <tr
                    key={a.id}
                    onClick={() => setSelected(a)}
                    className={cn(
                      'border-b border-slate-800/50 cursor-pointer hover:bg-slate-800/30 transition-colors',
                      a.status !== 'open' && 'opacity-60',
                    )}
                  >
                    <td className="py-2 px-2">
                      <RiskBadge level={a.risk_level} />
                    </td>
                    <td className="py-2 px-2 font-mono text-slate-200">{a.employee_id}</td>
                    <td className="py-2 px-2 text-slate-300 truncate max-w-md">
                      {a.top_signal ?? '—'}
                    </td>
                    <td className="py-2 px-2 font-mono text-right tabular-nums text-slate-100">
                      {a.display_score.toFixed(2)}
                    </td>
                    <td className="py-2 px-2 text-xs text-slate-400 capitalize">{a.status}</td>
                    <td className="py-2 px-2 text-xs text-slate-400 font-mono">
                      {timeAgo(a.triggered_at)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      <AlertSlideOver
        alert={selected}
        open={!!selected}
        onClose={() => setSelected(null)}
      />
    </div>
  );
}

function SegmentedControl({
  value,
  onChange,
  options,
}: {
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <div className="inline-flex rounded-lg bg-slate-900/60 border border-slate-800 p-0.5">
      {options.map((o) => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          className={cn(
            'px-3 py-1 text-xs rounded-md transition-colors',
            value === o.value
              ? 'bg-accent text-white'
              : 'text-slate-400 hover:text-slate-100',
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

function SortHeader({
  label,
  k,
  sortKey,
  sortDir,
  onClick,
  className,
  align,
}: {
  label: string;
  k: SortKey;
  sortKey: SortKey;
  sortDir: 'asc' | 'desc';
  onClick: (k: SortKey) => void;
  className?: string;
  align?: 'left' | 'right';
}) {
  return (
    <th className={cn('py-2 px-2', align === 'right' ? 'text-right' : 'text-left', className)}>
      <button
        onClick={() => onClick(k)}
        className={cn(
          'inline-flex items-center gap-1 hover:text-slate-200 transition-colors',
          sortKey === k && 'text-accent',
        )}
      >
        {label}
        {sortKey === k && (sortDir === 'asc' ? <ArrowUp size={11} /> : <ArrowDown size={11} />)}
      </button>
    </th>
  );
}
