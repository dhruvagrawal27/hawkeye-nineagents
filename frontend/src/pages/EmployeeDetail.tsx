import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, RefreshCw } from 'lucide-react';
import { employeesApi, narrativeApi } from '@/lib/api';
import { ScoreGauge } from '@/components/ui/ScoreGauge';
import { RiskBadge } from '@/components/ui/RiskBadge';
import { Skeleton } from '@/components/ui/Skeleton';
import { ShapWaterfall } from '@/components/charts/ShapWaterfall';
import { ScoreTimeline } from '@/components/charts/ScoreTimeline';
import { cn, timeAgo } from '@/lib/format';
import { toast } from '@/components/ui/Toast';

type Tab = 'timeline' | 'shap' | 'narrative' | 'alerts';

const TABS: { key: Tab; label: string }[] = [
  { key: 'timeline', label: 'Timeline' },
  { key: 'shap', label: 'SHAP analysis' },
  { key: 'narrative', label: 'Investigation memo' },
  { key: 'alerts', label: 'Alert history' },
];

export function EmployeeDetail() {
  const { id = '' } = useParams<{ id: string }>();
  const [tab, setTab] = useState<Tab>('timeline');

  const employee = useQuery({ queryKey: ['employee', id], queryFn: () => employeesApi.get(id) });
  const history = useQuery({ queryKey: ['employee', id, 'history'], queryFn: () => employeesApi.scoreHistory(id) });
  const alerts = useQuery({ queryKey: ['employee', id, 'alerts'], queryFn: () => employeesApi.alerts(id) });

  const latestAlert = alerts.data?.[0];
  const factors = latestAlert?.shap_factors ?? [];

  return (
    <div className="space-y-6">
      <Link to="/employees" className="inline-flex items-center gap-1 text-xs text-slate-400 hover:text-slate-100 transition-colors">
        <ArrowLeft size={14} /> All employees
      </Link>

      <header className="panel p-6 flex items-center gap-6 flex-wrap">
        {employee.isLoading ? (
          <Skeleton className="h-40 w-40 rounded-full" />
        ) : (
          <ScoreGauge
            score={employee.data?.display_score ?? 0}
            level={employee.data?.risk_level ?? 'LOW'}
          />
        )}
        <div className="flex-1 min-w-0">
          {employee.isLoading ? (
            <>
              <Skeleton className="h-7 w-64 mb-2" />
              <Skeleton className="h-4 w-32" />
            </>
          ) : (
            <>
              <div className="flex items-center gap-3 mb-1">
                <h1 className="text-2xl font-semibold text-slate-100">{employee.data?.display_name}</h1>
                {employee.data?.risk_level && <RiskBadge level={employee.data.risk_level} size="md" />}
              </div>
              <div className="font-mono text-xs text-slate-400">{employee.data?.id}</div>
              <div className="text-2xs uppercase tracking-widest text-amber-400/80 mt-1 font-mono">
                Bank employee · privileged-access monitoring
              </div>
              <div className="mt-3 flex gap-6 text-xs">
                <Stat label="Department" value={employee.data?.department} />
                <Stat label="Open alerts" value={String(employee.data?.open_alert_count ?? 0)} />
                <Stat label="Total alerts" value={String(alerts.data?.length ?? 0)} />
                <Stat
                  label="Mule label"
                  value={employee.data?.is_mule_seed ? 'Confirmed mule' : 'Not flagged'}
                />
              </div>
            </>
          )}
        </div>
      </header>

      <nav className="flex gap-1 border-b border-slate-800">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={cn(
              'px-4 py-2 text-sm transition-colors border-b-2 -mb-px',
              tab === t.key
                ? 'border-accent text-slate-100'
                : 'border-transparent text-slate-400 hover:text-slate-200',
            )}
          >
            {t.label}
          </button>
        ))}
      </nav>

      <section className="panel p-5">
        {tab === 'timeline' && (
          <>
            <h2 className="text-sm uppercase tracking-wider text-slate-400 mb-4">Score over time</h2>
            {history.isLoading ? <Skeleton className="h-64 w-full" /> : <ScoreTimeline points={history.data ?? []} />}
          </>
        )}

        {tab === 'shap' && (
          <>
            <h2 className="text-sm uppercase tracking-wider text-slate-400 mb-4">Latest model factors</h2>
            {alerts.isLoading ? <Skeleton className="h-32 w-full" /> : <ShapWaterfall factors={factors} />}
            {factors.length > 0 && (
              <p className="text-xs text-slate-500 mt-4 italic">
                Factors are sorted by absolute contribution. Red bars push score up; green bars push it down.
              </p>
            )}
          </>
        )}

        {tab === 'narrative' && latestAlert && (
          <NarrativeTab alertId={latestAlert.id} />
        )}
        {tab === 'narrative' && !latestAlert && (
          <div className="text-sm text-slate-500 italic text-center py-8">
            No alerts yet for this employee — replay a few minutes of activity to generate one.
          </div>
        )}

        {tab === 'alerts' && (
          <>
            <h2 className="text-sm uppercase tracking-wider text-slate-400 mb-4">All alerts</h2>
            {alerts.isLoading ? (
              <Skeleton className="h-32 w-full" />
            ) : (alerts.data ?? []).length === 0 ? (
              <div className="text-sm text-slate-500 italic text-center py-8">No alerts yet.</div>
            ) : (
              <div className="space-y-2">
                {(alerts.data ?? []).map((a) => (
                  <div key={a.id} className="flex items-center justify-between border-b border-slate-800/50 pb-2">
                    <div className="flex items-center gap-3">
                      <RiskBadge level={a.risk_level} />
                      <span className="text-xs text-slate-400 font-mono">#{a.id}</span>
                      <span className="text-sm text-slate-200">{a.top_signal ?? '—'}</span>
                    </div>
                    <div className="text-xs text-slate-500 font-mono">
                      {a.display_score.toFixed(2)} · {timeAgo(a.triggered_at)} · {a.status}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </section>
    </div>
  );
}

function NarrativeTab({ alertId }: { alertId: number }) {
  const qc = useQueryClient();
  const narrative = useQuery({
    queryKey: ['narrative', alertId],
    queryFn: () => narrativeApi.get(alertId),
  });

  const regen = useMutation({
    mutationFn: () => narrativeApi.regenerate(alertId),
    onSuccess: () => {
      toast('Narrative regenerated', { variant: 'success' });
      qc.invalidateQueries({ queryKey: ['narrative', alertId] });
    },
    onError: () => toast('Failed to regenerate', { variant: 'critical' }),
  });

  return (
    <>
      <header className="flex items-center justify-between mb-4">
        <h2 className="text-sm uppercase tracking-wider text-slate-400">Investigation memo</h2>
        <button
          onClick={() => regen.mutate()}
          disabled={regen.isPending}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-slate-800 hover:bg-slate-700 text-xs text-slate-200 disabled:opacity-50 transition-colors"
        >
          <RefreshCw size={12} className={regen.isPending ? 'animate-spin' : ''} />
          Regenerate
        </button>
      </header>
      {narrative.isLoading || regen.isPending ? (
        <div>
          <Skeleton className="h-4 w-32 mb-3" />
          <Skeleton className="h-3 w-full mb-1.5" />
          <Skeleton className="h-3 w-full mb-1.5" />
          <Skeleton className="h-3 w-3/4 mb-4" />
          <Skeleton className="h-4 w-32 mb-3" />
          <Skeleton className="h-3 w-full mb-1.5" />
          <Skeleton className="h-3 w-full mb-1.5" />
          <Skeleton className="h-3 w-2/3" />
        </div>
      ) : narrative.data ? (
        <div>
          <div className="prose prose-sm prose-invert max-w-none text-sm leading-relaxed whitespace-pre-wrap">
            {narrative.data.body}
          </div>
          <div className="mt-4 pt-3 border-t border-slate-800 flex gap-3 text-xs text-slate-500 font-mono">
            <span>model: {narrative.data.model_version}</span>
            {narrative.data.latency_ms && <span>latency: {narrative.data.latency_ms}ms</span>}
            {narrative.data.is_fallback && <span className="text-amber-400">⚠ fallback</span>}
          </div>
        </div>
      ) : (
        <div className="text-sm text-slate-500 italic">Failed to load narrative.</div>
      )}
    </>
  );
}

function Stat({ label, value }: { label: string; value?: string }) {
  return (
    <div>
      <div className="uppercase tracking-widest text-slate-500 text-[10px]">{label}</div>
      <div className="text-slate-200 font-medium">{value ?? '—'}</div>
    </div>
  );
}
