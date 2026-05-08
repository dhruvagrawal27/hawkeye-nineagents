import { useQuery } from '@tanstack/react-query';
import { CheckCircle2, AlertCircle, XCircle } from 'lucide-react';
import { settingsApi } from '@/lib/api';
import { Skeleton } from '@/components/ui/Skeleton';

export function SettingsPage() {
  const card = useQuery({ queryKey: ['model-card'], queryFn: settingsApi.modelCard });
  const ready = useQuery({
    queryKey: ['readyz'],
    queryFn: settingsApi.ready,
    refetchInterval: 10_000,
  });

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-slate-100">System & model settings</h1>
        <p className="text-sm text-slate-400 mt-1">
          Read-only view of model lineage, threshold, and live service health.
        </p>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Model card */}
        <section className="panel p-5">
          <h2 className="text-sm uppercase tracking-wider text-slate-400 mb-4">Model card</h2>
          {card.isLoading ? (
            <Skeleton className="h-48 w-full" />
          ) : (
            <dl className="grid grid-cols-2 gap-y-3 gap-x-6 text-sm">
              <Item label="Name"        value={card.data?.name} />
              <Item label="Version"     value={card.data?.version} />
              <Item label="Threshold"   value={card.data?.threshold?.toFixed(6)} mono />
              <Item label="AUC"         value={card.data?.auc} />
              <Item label="F1"          value={card.data?.f1} />
              <Item label="Trained"     value={card.data?.training_date} />
              <Item label="Features (full)"  value={card.data?.n_features_full} mono />
              <Item label="Features (clean)" value={card.data?.n_features_clean} mono />
              <Item
                label="Blend weights"
                value={
                  card.data?.blend_weights
                    ? `m1=${card.data.blend_weights.m1.toFixed(2)}  m2=${card.data.blend_weights.m2.toFixed(2)}`
                    : '—'
                }
                mono
              />
            </dl>
          )}
        </section>

        {/* System health */}
        <section className="panel p-5">
          <header className="flex items-center justify-between mb-4">
            <h2 className="text-sm uppercase tracking-wider text-slate-400">System health</h2>
            <span className="text-xs font-mono text-slate-500">
              {ready.data?.status === 'ok' ? 'all services up' : 'check below'}
            </span>
          </header>
          {ready.isLoading ? (
            <Skeleton className="h-48 w-full" />
          ) : (
            <ul className="space-y-2 text-sm">
              {Object.entries(ready.data?.services ?? {}).map(([name, svc]: any) => (
                <li
                  key={name}
                  className="flex items-center justify-between border-b border-slate-800/50 pb-2"
                >
                  <div className="flex items-center gap-2.5">
                    <StatusIcon status={svc.status} />
                    <span className="font-mono text-slate-200 uppercase text-xs tracking-wide">
                      {name}
                    </span>
                  </div>
                  <span
                    className={
                      svc.status === 'ok'
                        ? 'text-xs text-emerald-400'
                        : svc.status === 'down'
                        ? 'text-xs text-red-400'
                        : 'text-xs text-amber-400'
                    }
                  >
                    {svc.detail || svc.status}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      {/* Compliance footer */}
      <section className="panel p-5 border-amber-900/40 bg-amber-950/10">
        <h3 className="text-xs uppercase tracking-widest text-amber-300/80 mb-2">
          Compliance posture
        </h3>
        <p className="text-sm text-slate-300 leading-relaxed">
          HAWKEYE operates under a strict <strong className="text-slate-100">human-in-the-loop</strong> policy.
          All automated risk scores must be reviewed by a human analyst before any operational action is taken.
          Every alert ships with a SHAP factor breakdown and a model-generated investigation memo for auditability.
          Compliant with RBI FREE-AI guidelines, ITV-2 SSO requirements, and the bank's internal model risk
          management framework.
        </p>
        <p className="text-xs text-slate-500 mt-3 font-mono">
          NINEAGENTS · RBI NFPC Phase 2 · Rank #4 nationally · AUC 0.998 · F1 0.967 on 400M+ transactions
        </p>
      </section>
    </div>
  );
}

function Item({ label, value, mono }: { label: string; value?: any; mono?: boolean }) {
  return (
    <>
      <dt className="text-xs uppercase tracking-widest text-slate-500">{label}</dt>
      <dd className={mono ? 'font-mono text-slate-100' : 'text-slate-100'}>{value ?? '—'}</dd>
    </>
  );
}

function StatusIcon({ status }: { status: string }) {
  if (status === 'ok') return <CheckCircle2 size={16} className="text-emerald-400" />;
  if (status === 'down') return <XCircle size={16} className="text-red-400" />;
  return <AlertCircle size={16} className="text-amber-400" />;
}
