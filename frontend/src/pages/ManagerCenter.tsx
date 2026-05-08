import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { ChevronUp, Building2, ShieldAlert, Inbox, ClipboardCheck } from 'lucide-react';
import {
  alertsApi,
  statsApi,
  type Alert as AlertT,
  type AuditEntry,
  type DeptRollup,
} from '@/lib/api';
import { useRealtimeAlerts } from '@/hooks/useRealtimeAlerts';
import { LiveEventTicker } from '@/components/replay/LiveEventTicker';
import { EventRateChart } from '@/components/charts/EventRateChart';
import { AlertHeatmap } from '@/components/charts/AlertHeatmap';
import { MissionCallout } from '@/components/layout/MissionCallout';
import { RiskBadge } from '@/components/ui/RiskBadge';
import { Skeleton } from '@/components/ui/Skeleton';
import { toast } from '@/components/ui/Toast';
import { cn, timeAgo } from '@/lib/format';

/**
 * Bank Manager command-center: bird's-eye supervision view.
 * Designed so a Branch Manager can monitor + take action without
 * drilling into individual alerts.
 */
export function ManagerCenter() {
  const overview = useQuery({ queryKey: ['stats', 'overview'], queryFn: statsApi.overview, refetchInterval: 4_000 });
  const depts = useQuery({ queryKey: ['stats', 'depts'], queryFn: statsApi.byDepartment, refetchInterval: 10_000 });
  const hourly = useQuery({ queryKey: ['stats', 'hourly'], queryFn: () => statsApi.hourly(168), refetchInterval: 30_000 });
  const escalated = useQuery({ queryKey: ['queue', 'escalated'], queryFn: () => alertsApi.escalatedQueue(20), refetchInterval: 10_000 });
  const audit = useQuery({ queryKey: ['audit', 'recent'], queryFn: () => statsApi.auditLog(30), refetchInterval: 10_000 });

  useRealtimeAlerts(40); // keep the WS warm; ticker uses it

  return (
    <div className="space-y-3">
      <MissionCallout />

      {/* Header strip — bank manager identity & big numbers */}
      <header className="panel px-4 py-3 flex items-center gap-4">
        <Building2 size={20} className="text-accent" />
        <div className="flex-1 min-w-0">
          <h1 className="text-base font-semibold text-ink">Branch Command Center · Insider Fraud</h1>
          <p className="text-2xs text-dim font-mono uppercase tracking-widest">
            Real-time supervision of bank employees with privileged access · approve &amp; escalate
          </p>
        </div>
        <CommandStat label="OPEN"          value={overview.data?.alerts_open}        tone="info" />
        <CommandStat label="ESCALATED"     value={overview.data?.alerts_escalated}   tone="warn" />
        <CommandStat label="HIGH-RISK EMP" value={overview.data?.high_risk_employees} />
        <CommandStat label="EVENTS"        value={overview.data?.events_ingested} />
      </header>

      {/* Row 1: live rate + escalation queue */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-3">
        <div className="xl:col-span-2 grid grid-cols-1 lg:grid-cols-2 gap-3">
          <EventRateChart height={140} />
          <div className="panel p-3">
            <header className="flex items-center justify-between mb-2">
              <span className="eyebrow">Score distribution · open alerts</span>
              <span className="text-2xs font-mono text-dim">{overview.data?.alerts_open ?? 0} open</span>
            </header>
            <RiskMiniBars />
          </div>
        </div>

        {/* Approval queue */}
        <ApprovalQueue alerts={escalated.data ?? []} loading={escalated.isLoading} />
      </div>

      {/* Row 2: department rollup table + heatmap */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-3">
        <DepartmentRollup data={depts.data ?? []} loading={depts.isLoading} />
        <div className="panel p-3 xl:col-span-2">
          <header className="flex items-center justify-between mb-3">
            <span className="eyebrow">Alert volume · 7d × 24h heatmap</span>
            <span className="text-2xs font-mono text-dim">
              cell = total alerts for that hour-of-day
            </span>
          </header>
          {hourly.isLoading ? (
            <Skeleton className="h-32" />
          ) : (
            <AlertHeatmap data={hourly.data ?? []} />
          )}
        </div>
      </div>

      {/* Row 3: live tape + audit feed */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-3">
        <div className="xl:col-span-2">
          <LiveEventTicker height={420} />
        </div>
        <AuditFeed entries={audit.data ?? []} loading={audit.isLoading} />
      </div>
    </div>
  );
}

function CommandStat({
  label,
  value,
  tone,
}: {
  label: string;
  value: number | undefined;
  tone?: 'info' | 'warn';
}) {
  const colorClass =
    tone === 'warn' ? 'text-amber-300' : tone === 'info' ? 'text-accent' : 'text-ink';
  return (
    <div className="text-right">
      <div className="text-3xs font-mono uppercase tracking-widest text-dim">{label}</div>
      <div className={cn('font-mono text-xl tabular-nums', colorClass)}>{value ?? '—'}</div>
    </div>
  );
}

function RiskMiniBars() {
  const dist = useQuery({
    queryKey: ['stats', 'risk-distribution', 'mini'],
    queryFn: statsApi.riskDistribution,
    refetchInterval: 10_000,
  });
  const max = Math.max(...(dist.data ?? []).map((d) => d.count), 1);
  return (
    <div className="space-y-0.5 font-mono text-2xs">
      {(dist.data ?? []).map((b, i) => {
        const w = (b.count / max) * 100;
        const cls =
          b.bin_low >= 0.85 ? 'bg-risk-critical/70' :
          b.bin_low >= 0.7  ? 'bg-risk-high/70'     :
          b.bin_low >= 0.5  ? 'bg-risk-medium/70'   :
                              'bg-risk-low/40';
        return (
          <div key={i} className="flex items-center gap-1.5">
            <span className="w-9 text-right tabular-nums text-dim">{b.bin_low.toFixed(2)}</span>
            <div className="flex-1 h-1.5 bg-line/40 rounded-sm overflow-hidden">
              <div className={cls} style={{ width: `${w}%` }} />
            </div>
            <span className="w-7 text-right tabular-nums text-ink">{b.count}</span>
          </div>
        );
      })}
    </div>
  );
}

function ApprovalQueue({ alerts, loading }: { alerts: AlertT[]; loading: boolean }) {
  const qc = useQueryClient();
  const approve = useMutation({
    mutationFn: (id: number) => alertsApi.triage(id, 'investigate', 'approved by manager'),
    onSuccess: () => {
      toast('Approved — assigned for investigation', { variant: 'success' });
      qc.invalidateQueries({ queryKey: ['queue', 'escalated'] });
      qc.invalidateQueries({ queryKey: ['alerts'] });
    },
  });
  const reject = useMutation({
    mutationFn: (id: number) => alertsApi.triage(id, 'dismiss', 'rejected by manager'),
    onSuccess: () => {
      toast('Rejected — alert dismissed', { variant: 'info' });
      qc.invalidateQueries({ queryKey: ['queue', 'escalated'] });
      qc.invalidateQueries({ queryKey: ['alerts'] });
    },
  });

  return (
    <div className="panel p-0 overflow-hidden">
      <header className="flex items-center justify-between px-3 py-1.5 border-b border-line/60 bg-panel2/40">
        <span className="eyebrow flex items-center gap-2">
          <ShieldAlert size={12} className="text-amber-400" /> Approval queue
        </span>
        <span className="text-3xs font-mono text-dim">{alerts.length} pending</span>
      </header>
      <div className="max-h-[300px] overflow-y-auto">
        {loading ? (
          <div className="p-3"><Skeleton className="h-32" /></div>
        ) : alerts.length === 0 ? (
          <div className="p-6 text-center text-dim text-2xs italic">No escalations awaiting approval.</div>
        ) : (
          alerts.map((a) => (
            <div key={a.id} className="px-3 py-2 border-b border-line/30 row-hover">
              <div className="flex items-center justify-between gap-2 mb-1">
                <div className="flex items-center gap-2 min-w-0">
                  <RiskBadge level={a.risk_level} />
                  <Link to={`/employees/${a.employee_id}`} className="font-mono text-2xs text-ink hover:text-accent truncate">
                    {a.employee_id}
                  </Link>
                </div>
                <span className="font-mono text-2xs tabular-nums text-rose-300">{a.display_score.toFixed(2)}</span>
              </div>
              <div className="text-2xs text-dim truncate">{a.top_signal ?? 'Signal pending'}</div>
              <div className="flex gap-1.5 mt-1.5">
                <button
                  onClick={() => approve.mutate(a.id)}
                  disabled={approve.isPending}
                  className="flex-1 px-2 py-1 rounded bg-accent/80 hover:bg-accent text-2xs font-mono uppercase tracking-widest text-white disabled:opacity-50"
                >
                  Approve
                </button>
                <button
                  onClick={() => reject.mutate(a.id)}
                  disabled={reject.isPending}
                  className="flex-1 px-2 py-1 rounded bg-line/60 hover:bg-line text-2xs font-mono uppercase tracking-widest text-dim hover:text-ink disabled:opacity-50"
                >
                  Reject
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function DepartmentRollup({ data, loading }: { data: DeptRollup[]; loading: boolean }) {
  const sorted = useMemo(() => [...data].sort((a, b) => b.open - a.open), [data]);
  return (
    <div className="panel p-0 overflow-hidden">
      <header className="flex items-center justify-between px-3 py-1.5 border-b border-line/60 bg-panel2/40">
        <span className="eyebrow flex items-center gap-2">
          <Inbox size={12} className="text-accent" /> Department rollup
        </span>
      </header>
      {loading ? (
        <div className="p-3"><Skeleton className="h-40" /></div>
      ) : (
        <table className="w-full text-2xs font-mono">
          <thead>
            <tr className="border-b border-line/40 text-dim">
              <th className="text-left  px-3 py-1.5">DEPARTMENT</th>
              <th className="text-right px-3 py-1.5 w-12">OPEN</th>
              <th className="text-right px-3 py-1.5 w-10">CRIT</th>
              <th className="text-right px-3 py-1.5 w-10">HIGH</th>
              <th className="text-right px-3 py-1.5 w-10">EMP</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((d) => (
              <tr key={d.department} className="border-b border-line/30 row-hover">
                <td className="px-3 py-1 text-ink">{d.department}</td>
                <td className="px-3 py-1 text-right tabular-nums text-ink">{d.open}</td>
                <td className="px-3 py-1 text-right tabular-nums text-risk-critical">{d.critical}</td>
                <td className="px-3 py-1 text-right tabular-nums text-risk-high">{d.high}</td>
                <td className="px-3 py-1 text-right tabular-nums text-dim">{d.unique_employees}</td>
              </tr>
            ))}
            {sorted.length === 0 && (
              <tr><td colSpan={5} className="text-center text-dim italic py-6 text-2xs">No departments yet.</td></tr>
            )}
          </tbody>
        </table>
      )}
    </div>
  );
}

function AuditFeed({ entries, loading }: { entries: AuditEntry[]; loading: boolean }) {
  return (
    <div className="panel p-0 overflow-hidden">
      <header className="flex items-center justify-between px-3 py-1.5 border-b border-line/60 bg-panel2/40">
        <span className="eyebrow flex items-center gap-2">
          <ClipboardCheck size={12} className="text-accent" /> Audit feed
        </span>
        <span className="text-3xs font-mono text-dim">last {entries.length}</span>
      </header>
      <div className="max-h-[420px] overflow-y-auto font-mono text-2xs">
        {loading ? (
          <div className="p-3"><Skeleton className="h-32" /></div>
        ) : entries.length === 0 ? (
          <div className="p-6 text-center text-dim italic">No actions taken yet.</div>
        ) : (
          entries.map((e) => (
            <div key={e.id} className="px-3 py-1.5 border-b border-line/30 flex items-start gap-2">
              <ChevronUp size={11} className="text-accent mt-0.5 shrink-0" />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-ink truncate">{e.actor}</span>
                  <span className="text-amber-300 uppercase tracking-wider">{e.action}</span>
                  {e.alert_id && (
                    <span className="text-dim">· #{e.alert_id}</span>
                  )}
                </div>
                {e.detail && <div className="text-dim truncate mt-0.5">{e.detail}</div>}
              </div>
              <span className="text-dim shrink-0 tabular-nums">{timeAgo(e.occurred_at)}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
