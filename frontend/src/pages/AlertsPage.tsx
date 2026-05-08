import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowDown, ArrowUp, CheckSquare, Search, Square } from 'lucide-react';
import type { Alert } from '@/lib/api';
import { alertsApi } from '@/lib/api';
import { useRealtimeAlerts } from '@/hooks/useRealtimeAlerts';
import { useRole } from '@/store/roleStore';
import { RiskBadge } from '@/components/ui/RiskBadge';
import { Skeleton } from '@/components/ui/Skeleton';
import { AlertSlideOver } from '@/components/alerts/AlertSlideOver';
import { toast } from '@/components/ui/Toast';
import { cn, timeAgo } from '@/lib/format';

type SortKey = 'triggered_at' | 'score' | 'risk_level' | 'employee_id';

const RISK_RANK: Record<string, number> = { CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1 };

export function AlertsPage() {
  const role = useRole();
  const qc = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [riskFilter, setRiskFilter] = useState<string>('all');
  const [search, setSearch] = useState('');
  const [sortKey, setSortKey] = useState<SortKey>('triggered_at');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const [selected, setSelected] = useState<Alert | null>(null);
  const [checked, setChecked] = useState<Set<number>>(new Set());

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
    if (sortKey === key) setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
    else { setSortKey(key); setSortDir('desc'); }
  };

  const allSelected = filtered.length > 0 && filtered.every((a) => checked.has(a.id));
  const toggleAll = () => {
    if (allSelected) setChecked(new Set());
    else setChecked(new Set(filtered.map((a) => a.id)));
  };
  const toggleOne = (id: number) =>
    setChecked((s) => {
      const next = new Set(s);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });

  const bulk = useMutation({
    mutationFn: (action: 'dismiss' | 'investigate' | 'escalate') =>
      alertsApi.bulkTriage(Array.from(checked), action, `bulk by ${role.username}`),
    onSuccess: (data, action) => {
      toast(`Bulk ${action}: ${data.updated} alerts updated`, { variant: 'success' });
      setChecked(new Set());
      qc.invalidateQueries({ queryKey: ['alerts'] });
      qc.invalidateQueries({ queryKey: ['queue'] });
    },
    onError: () => toast('Bulk action failed', { variant: 'critical' }),
  });

  return (
    <div className="space-y-3">
      <header className="flex items-end justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-xl font-semibold text-ink">Alerts</h1>
          <p className="text-2xs font-mono text-dim mt-0.5 uppercase tracking-widest">
            {filtered.length} of {query.data?.length ?? 0} · {checked.size} selected · viewing as {role.label}
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

      <div className="panel p-3">
        {/* Bulk action bar — appears only when something is checked */}
        {checked.size > 0 && (
          <div className="mb-2 flex items-center justify-between gap-2 px-3 py-1.5 rounded bg-accent/10 border border-accent/30">
            <span className="text-2xs font-mono uppercase tracking-widest text-ink">
              {checked.size} selected
            </span>
            <div className="flex gap-1.5">
              {role.canBulkAction ? (
                <>
                  <BulkBtn label="Investigate" onClick={() => bulk.mutate('investigate')} disabled={bulk.isPending} />
                  {role.canEscalate && (
                    <BulkBtn label="Escalate" onClick={() => bulk.mutate('escalate')} disabled={bulk.isPending} tone="warn" />
                  )}
                  <BulkBtn label="Dismiss" onClick={() => bulk.mutate('dismiss')} disabled={bulk.isPending} tone="dim" />
                </>
              ) : (
                <span className="text-2xs font-mono text-dim italic">
                  Bulk actions require Supervisor or Manager role
                </span>
              )}
              <BulkBtn label="Clear" onClick={() => setChecked(new Set())} tone="dim" />
            </div>
          </div>
        )}

        <div className="relative mb-2">
          <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-dim" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by employee or account ID…"
            className="w-full bg-panel2/60 border border-line/80 rounded pl-9 pr-3 py-1.5 text-2xs font-mono placeholder-dim/60 text-ink focus:outline-none focus:border-accent transition-colors"
          />
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-2xs font-mono">
            <thead>
              <tr className="text-3xs uppercase tracking-widest text-dim border-b border-line/60">
                {role.canBulkAction && (
                  <th className="px-2 py-1.5 w-6">
                    <button onClick={toggleAll} className="text-dim hover:text-ink">
                      {allSelected ? <CheckSquare size={12} /> : <Square size={12} />}
                    </button>
                  </th>
                )}
                <SortHeader label="Risk" k="risk_level" sortKey={sortKey} sortDir={sortDir} onClick={toggleSort} className="w-16" />
                <SortHeader label="Employee" k="employee_id" sortKey={sortKey} sortDir={sortDir} onClick={toggleSort} className="w-32" />
                <th className="text-left py-1.5 px-2">Top signal</th>
                <SortHeader label="Score" k="score" sortKey={sortKey} sortDir={sortDir} onClick={toggleSort} className="w-16 text-right" align="right" />
                <th className="text-left py-1.5 px-2 w-24">Status</th>
                <SortHeader label="Triggered" k="triggered_at" sortKey={sortKey} sortDir={sortDir} onClick={toggleSort} className="w-24" />
              </tr>
            </thead>
            <tbody>
              {query.isLoading ? (
                Array.from({ length: 8 }).map((_, i) => (
                  <tr key={i}><td colSpan={7} className="py-1"><Skeleton className="h-7 w-full" /></td></tr>
                ))
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan={7} className="text-center py-8 text-dim text-2xs italic">
                    No alerts match the current filters.
                  </td>
                </tr>
              ) : (
                filtered.map((a) => (
                  <tr
                    key={a.id}
                    className={cn(
                      'border-b border-line/30 row-hover',
                      checked.has(a.id) && 'bg-accent/5',
                      a.status !== 'open' && 'opacity-60',
                    )}
                  >
                    {role.canBulkAction && (
                      <td className="px-2 py-1">
                        <button
                          onClick={() => toggleOne(a.id)}
                          className="text-dim hover:text-accent"
                        >
                          {checked.has(a.id) ? <CheckSquare size={12} /> : <Square size={12} />}
                        </button>
                      </td>
                    )}
                    <td className="px-2 py-1 cursor-pointer" onClick={() => setSelected(a)}>
                      <RiskBadge level={a.risk_level} />
                    </td>
                    <td className="px-2 py-1 text-ink cursor-pointer" onClick={() => setSelected(a)}>{a.employee_id}</td>
                    <td className="px-2 py-1 text-dim truncate max-w-md cursor-pointer" onClick={() => setSelected(a)}>
                      {a.top_signal ?? '—'}
                    </td>
                    <td className="px-2 py-1 text-right tabular-nums text-ink cursor-pointer" onClick={() => setSelected(a)}>
                      {a.display_score.toFixed(2)}
                    </td>
                    <td className="px-2 py-1 text-dim uppercase">{a.status}</td>
                    <td className="px-2 py-1 text-dim">{timeAgo(a.triggered_at)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      <AlertSlideOver alert={selected} open={!!selected} onClose={() => setSelected(null)} />
    </div>
  );
}

function BulkBtn({
  label, onClick, disabled, tone,
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  tone?: 'warn' | 'dim';
}) {
  const cls =
    tone === 'warn' ? 'bg-amber-600 hover:bg-amber-500 text-white' :
    tone === 'dim'  ? 'bg-line/60 hover:bg-line text-dim hover:text-ink' :
                      'bg-accent hover:bg-accent2 text-white';
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={cn(
        'px-3 py-1 rounded text-2xs font-mono uppercase tracking-widest disabled:opacity-50 transition-colors',
        cls,
      )}
    >
      {label}
    </button>
  );
}

function SegmentedControl({
  value, onChange, options,
}: {
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <div className="inline-flex rounded bg-panel2/60 border border-line/60 p-0.5">
      {options.map((o) => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          className={cn(
            'px-2.5 py-1 text-2xs font-mono uppercase tracking-widest rounded transition-colors',
            value === o.value ? 'bg-accent text-white' : 'text-dim hover:text-ink',
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

function SortHeader({
  label, k, sortKey, sortDir, onClick, className, align,
}: {
  label: string; k: SortKey; sortKey: SortKey; sortDir: 'asc' | 'desc';
  onClick: (k: SortKey) => void; className?: string; align?: 'left' | 'right';
}) {
  return (
    <th className={cn('py-1.5 px-2', align === 'right' ? 'text-right' : 'text-left', className)}>
      <button
        onClick={() => onClick(k)}
        className={cn('inline-flex items-center gap-1 hover:text-ink transition-colors', sortKey === k && 'text-accent')}
      >
        {label}
        {sortKey === k && (sortDir === 'asc' ? <ArrowUp size={10} /> : <ArrowDown size={10} />)}
      </button>
    </th>
  );
}
