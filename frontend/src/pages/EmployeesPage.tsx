import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Search, ArrowRight } from 'lucide-react';
import { employeesApi, type Employee } from '@/lib/api';
import { RiskBadge } from '@/components/ui/RiskBadge';
import { Skeleton } from '@/components/ui/Skeleton';
import { cn } from '@/lib/format';

const DEPARTMENTS = ['All', 'Core Banking', 'Treasury', 'Loans', 'HRMS', 'Compliance'];

export function EmployeesPage() {
  const [department, setDepartment] = useState('All');
  const [search, setSearch] = useState('');

  const top = useQuery({ queryKey: ['employees', 'top'], queryFn: () => employeesApi.top(20) });
  const all = useQuery({
    queryKey: ['employees', 'list', department],
    queryFn: () => employeesApi.list({ limit: 200, department: department === 'All' ? undefined : department }),
  });

  const filtered = useMemo(() => {
    let rows = all.data ?? [];
    if (search.trim()) {
      const q = search.toLowerCase();
      rows = rows.filter(
        (r) => r.id.toLowerCase().includes(q) || r.display_name.toLowerCase().includes(q),
      );
    }
    return rows;
  }, [all.data, search]);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-slate-100">Employees</h1>
        <p className="text-sm text-slate-400 mt-1">
          {all.data?.length ?? 0} monitored ·{' '}
          {(all.data ?? []).filter((e) => (e.open_alert_count ?? 0) > 0).length} with open alerts
        </p>
      </header>

      {/* Top risk band */}
      <section className="panel p-5">
        <header className="flex items-center justify-between mb-4">
          <h2 className="text-sm uppercase tracking-wider text-slate-400">Highest current risk</h2>
          <span className="text-xs text-slate-500">Top {top.data?.length ?? 0}</span>
        </header>
        {top.isLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-20 w-full" />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {(top.data ?? []).map((e) => (
              <EmployeeChip key={e.id} employee={e} />
            ))}
          </div>
        )}
      </section>

      {/* Browse all */}
      <section className="panel p-5">
        <header className="flex items-center justify-between mb-4 gap-3 flex-wrap">
          <h2 className="text-sm uppercase tracking-wider text-slate-400">Browse</h2>
          <div className="flex gap-2">
            {DEPARTMENTS.map((d) => (
              <button
                key={d}
                onClick={() => setDepartment(d)}
                className={cn(
                  'px-3 py-1 text-xs rounded-md border transition-colors',
                  department === d
                    ? 'bg-accent text-white border-accent'
                    : 'bg-slate-900/30 text-slate-400 border-slate-800 hover:text-slate-100',
                )}
              >
                {d}
              </button>
            ))}
          </div>
        </header>

        <div className="relative mb-3">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by ID or name…"
            className="w-full bg-slate-900/50 border border-slate-800 rounded-lg pl-9 pr-3 py-2 text-sm placeholder-slate-500 focus:outline-none focus:border-accent transition-colors"
          />
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs uppercase tracking-wider text-slate-500 border-b border-slate-800">
                <th className="text-left py-2 px-2">Employee</th>
                <th className="text-left py-2 px-2 w-32">Department</th>
                <th className="text-right py-2 px-2 w-20">Score</th>
                <th className="text-left py-2 px-2 w-24">Risk</th>
                <th className="text-right py-2 px-2 w-20">Alerts</th>
                <th className="text-right py-2 px-2 w-12" />
              </tr>
            </thead>
            <tbody>
              {all.isLoading ? (
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
                    No employees match these filters.
                  </td>
                </tr>
              ) : (
                filtered.map((e) => (
                  <tr key={e.id} className="border-b border-slate-800/50 hover:bg-slate-800/30 transition-colors">
                    <td className="py-2 px-2">
                      <div className="font-mono text-xs text-slate-400">{e.id}</div>
                      <div className="text-slate-200">{e.display_name}</div>
                    </td>
                    <td className="py-2 px-2 text-slate-400 text-xs">{e.department}</td>
                    <td className="py-2 px-2 font-mono text-right tabular-nums text-slate-100">
                      {e.display_score == null ? '—' : e.display_score.toFixed(2)}
                    </td>
                    <td className="py-2 px-2">
                      {e.risk_level ? <RiskBadge level={e.risk_level} /> : <span className="text-slate-600 text-xs">—</span>}
                    </td>
                    <td className="py-2 px-2 text-right text-sm text-slate-300 font-mono">
                      {e.open_alert_count}
                    </td>
                    <td className="py-2 px-2 text-right">
                      <Link
                        to={`/employees/${e.id}`}
                        className="text-slate-500 hover:text-accent transition-colors inline-flex"
                      >
                        <ArrowRight size={14} />
                      </Link>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function EmployeeChip({ employee: e }: { employee: Employee }) {
  return (
    <Link
      to={`/employees/${e.id}`}
      className="panel hover:border-accent/40 transition-colors px-4 py-3 flex items-center gap-3"
    >
      <div className="flex-1 min-w-0">
        <div className="font-mono text-xs text-slate-500 truncate">{e.id}</div>
        <div className="text-sm text-slate-100 truncate">{e.display_name}</div>
        <div className="text-[10px] text-slate-500 mt-0.5">{e.department}</div>
      </div>
      <div className="text-right shrink-0">
        <div className="font-mono text-xl text-slate-50">
          {e.display_score != null ? e.display_score.toFixed(2) : '—'}
        </div>
        {e.risk_level && <RiskBadge level={e.risk_level} />}
      </div>
    </Link>
  );
}
