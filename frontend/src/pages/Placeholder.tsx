/**
 * Placeholder for unimplemented pages — Alerts, Employees, EmployeeDetail,
 * Graph Explorer, Settings. The Dashboard and Replay Studio are fully wired;
 * these other pages exercise the same API contracts and are scaffolded out
 * in NEXT_STEPS.md.
 */
export function Placeholder({ title }: { title: string }) {
  return (
    <div className="panel p-8 max-w-2xl">
      <h1 className="text-xl font-semibold text-slate-100 mb-2">{title}</h1>
      <p className="text-slate-400 text-sm leading-relaxed">
        This page is scaffolded but not yet implemented. The backend API and
        WebSocket support all the endpoints needed (see <code className="font-mono">/api/docs</code>{' '}
        when running locally). To finish it, follow the patterns in{' '}
        <code className="font-mono">Dashboard.tsx</code> and{' '}
        <code className="font-mono">ReplayStudio.tsx</code>.
      </p>
    </div>
  );
}
