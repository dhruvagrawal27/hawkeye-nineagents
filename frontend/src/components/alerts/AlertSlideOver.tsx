import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { ExternalLink, FileText } from 'lucide-react';
import type { Alert } from '@/lib/api';
import { alertsApi, api } from '@/lib/api';
import { SlideOver } from '@/components/ui/SlideOver';
import { ScoreGauge } from '@/components/ui/ScoreGauge';
import { ShapWaterfall } from '@/components/charts/ShapWaterfall';
import { RiskBadge } from '@/components/ui/RiskBadge';
import { Markdown } from '@/components/ui/Markdown';
import { ScoreComposition } from '@/components/alerts/ScoreComposition';
import { TEEAttestationBadge } from '@/components/alerts/TEEAttestationBadge';
import { timeAgo } from '@/lib/format';
import { toast } from '@/components/ui/Toast';

export function AlertSlideOver({
  alert,
  open,
  onClose,
}: {
  alert: Alert | null;
  open: boolean;
  onClose: () => void;
}) {
  const qc = useQueryClient();

  const narrative = useQuery({
    queryKey: ['narrative', alert?.id],
    queryFn: async () => (alert ? (await api.get(`/narrative/${alert.id}`)).data : null),
    enabled: !!alert && open,
  });

  const triage = useMutation({
    mutationFn: ({ action }: { action: 'dismiss' | 'investigate' | 'escalate' }) =>
      alertsApi.triage(alert!.id, action),
    onSuccess: (data, vars) => {
      toast(`Marked ${vars.action}`, { variant: 'success', body: `Alert #${alert!.id}` });
      qc.invalidateQueries({ queryKey: ['alerts'] });
    },
    onError: () => {
      toast('Failed to update alert', { variant: 'critical' });
    },
  });

  return (
    <SlideOver
      open={open}
      onClose={onClose}
      title={alert?.employee_id}
      subtitle={alert ? `Alert #${alert.id} · ${timeAgo(alert.triggered_at)}` : ''}
      width="wide"
    >
      {alert && (
        <div className="space-y-7">
          {/* Score + risk */}
          <section className="flex items-center gap-8">
            <ScoreGauge score={alert.display_score} level={alert.risk_level} />
            <div className="flex-1 space-y-2">
              <div className="flex items-center gap-2">
                <RiskBadge level={alert.risk_level} size="md" />
                <span className="text-xs text-slate-500 font-mono uppercase">
                  source: {alert.source}
                </span>
              </div>
              <div className="text-sm text-slate-300">
                <span className="text-slate-500">Top signal · </span>
                {alert.top_signal ?? '—'}
              </div>
              <Link
                to={`/employees/${alert.employee_id}`}
                className="inline-flex items-center gap-1 text-xs text-accent hover:text-accent2"
                onClick={onClose}
              >
                Open employee detail <ExternalLink size={12} />
              </Link>
            </div>
          </section>

          {/* Score composition: shows LightGBM vs T-HGNN vs SimCLR contributions */}
          <section>
            <ScoreComposition alert={alert} />
          </section>

          {/* SHAP */}
          <section>
            <h3 className="text-xs uppercase tracking-widest text-slate-400 mb-3">
              SHAP factor breakdown
              <span className="ml-2 text-2xs text-slate-500 normal-case font-mono">
                (LightGBM contribution per feature)
              </span>
            </h3>
            <ShapWaterfall factors={alert.shap_factors ?? []} />
          </section>

          {/* Narrative */}
          <section>
            <header className="flex items-center justify-between mb-3">
              <h3 className="text-xs uppercase tracking-widest text-slate-400">
                Investigation memo
              </h3>
              <FileText size={14} className="text-slate-500" />
            </header>
            {narrative.isLoading ? (
              <div className="text-xs text-slate-500 italic">Generating…</div>
            ) : narrative.data?.body ? (
              <>
                <Markdown source={narrative.data.body} />
                <TEEAttestationBadge narrative={narrative.data} />
              </>
            ) : (
              <div className="text-xs text-slate-500">
                Narrative will be generated on first view.
              </div>
            )}
          </section>

          {/* Triage actions */}
          <section className="flex gap-2 pt-3 border-t border-slate-800 sticky bottom-0 bg-panel py-3 -mx-6 px-6">
            <button
              onClick={() => triage.mutate({ action: 'investigate' })}
              disabled={triage.isPending}
              className="flex-1 px-3 py-2 rounded-lg bg-accent text-white text-sm font-medium hover:bg-accent2 disabled:opacity-50 transition-colors"
            >
              Investigate
            </button>
            <button
              onClick={() => triage.mutate({ action: 'escalate' })}
              disabled={triage.isPending}
              className="flex-1 px-3 py-2 rounded-lg bg-amber-600 text-white text-sm font-medium hover:bg-amber-500 disabled:opacity-50 transition-colors"
            >
              Escalate
            </button>
            <button
              onClick={() => triage.mutate({ action: 'dismiss' })}
              disabled={triage.isPending}
              className="flex-1 px-3 py-2 rounded-lg bg-slate-700 text-slate-200 text-sm font-medium hover:bg-slate-600 disabled:opacity-50 transition-colors"
            >
              Dismiss
            </button>
          </section>
        </div>
      )}
    </SlideOver>
  );
}
