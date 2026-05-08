import { useQuery } from '@tanstack/react-query';
import { CheckCircle2, AlertCircle, XCircle, ShieldCheck, User, Building2, Check, Minus } from 'lucide-react';
import { settingsApi } from '@/lib/api';
import { Skeleton } from '@/components/ui/Skeleton';
import { ROLES, useRole, useRoleStore, type Role } from '@/store/roleStore';
import { cn } from '@/lib/format';

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
        <section className="panel-paper p-5">
          <h2 className="text-sm uppercase tracking-wider text-amber-200/80 mb-4">Model card</h2>
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

      {/* Roles & permissions matrix */}
      <RolesMatrix />

      {/* Compliance footer */}
      <section className="panel-paper p-5">
        <h3 className="text-xs uppercase tracking-widest text-amber-200/80 mb-2">
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

function RolesMatrix() {
  const current = useRole();
  const setRole = useRoleStore((s) => s.setRole);
  const ROLE_ICONS: Record<Role, any> = {
    analyst: User,
    supervisor: ShieldCheck,
    manager: Building2,
  };

  const capabilities: { key: keyof typeof ROLES.analyst; label: string }[] = [
    { key: 'canDismiss',                label: 'Dismiss alerts' },
    { key: 'canInvestigate',            label: 'Open investigations (assign-to-self)' },
    { key: 'canEscalate',               label: 'Escalate to supervisor' },
    { key: 'canApproveEscalations',     label: 'Approve / reject escalations' },
    { key: 'canRegenerateNarrative',    label: 'Regenerate Groq narratives' },
    { key: 'canBulkAction',             label: 'Bulk triage (multiple alerts)' },
    { key: 'canViewAuditLog',           label: 'View audit log' },
    { key: 'canViewDepartmentRollup',   label: 'Department rollup + Command Center' },
  ];

  return (
    <section className="panel-paper p-5">
      <header className="mb-3">
        <h2 className="text-sm uppercase tracking-widest text-amber-200/80">Roles & permissions</h2>
        <p className="text-xs text-slate-400 mt-1">
          Active role:{' '}
          <span className="text-slate-100 font-mono">{current.label}</span>{' '}
          <span className="text-slate-500">({current.username})</span>.
          Click any column header to switch role for this browser session.
        </p>
      </header>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-line/60">
              <th className="text-left px-2 py-2 text-3xs uppercase tracking-widest text-dim">Capability</th>
              {(Object.values(ROLES) as typeof ROLES[Role][]).map((spec) => {
                const Icon = ROLE_ICONS[spec.id];
                const active = current.id === spec.id;
                return (
                  <th
                    key={spec.id}
                    onClick={() => setRole(spec.id)}
                    className={cn(
                      'text-left px-3 py-2 cursor-pointer transition-colors',
                      active ? 'bg-accent/10' : 'hover:bg-line/30',
                    )}
                  >
                    <div className="flex items-center gap-1.5">
                      <Icon size={12} className={active ? 'text-accent' : 'text-dim'} />
                      <span className="text-slate-100 font-medium">{spec.label}</span>
                      {active && <span className="text-3xs font-mono uppercase tracking-widest text-accent ml-auto">active</span>}
                    </div>
                    <div className="text-3xs font-mono text-slate-500 mt-0.5">{spec.username}</div>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {capabilities.map((cap) => (
              <tr key={cap.key as string} className="border-b border-line/30">
                <td className="px-2 py-1.5 text-slate-300">{cap.label}</td>
                {(Object.values(ROLES) as typeof ROLES[Role][]).map((spec) => {
                  const allowed = !!(spec[cap.key as keyof typeof spec] as boolean);
                  return (
                    <td key={spec.id} className="px-3 py-1.5">
                      {allowed ? (
                        <Check size={14} className="text-emerald-400" />
                      ) : (
                        <Minus size={14} className="text-slate-600" />
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-slate-500 mt-3 leading-relaxed">
        In production, the role comes from the Keycloak JWT (claim <code className="font-mono">realm_access.roles</code>).
        The local switcher above is for the demo only — when <code className="font-mono">PREFLIGHT_MODE=0</code> in the
        backend env, the API enforces role checks based on the bearer token.
      </p>
    </section>
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
