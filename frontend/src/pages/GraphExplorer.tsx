import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Search } from 'lucide-react';
import { graphApi } from '@/lib/api';
import { GraphCanvas } from '@/components/graph/GraphCanvas';
import { Skeleton } from '@/components/ui/Skeleton';
import { cn } from '@/lib/format';

export function GraphExplorer() {
  const [minScore, setMinScore] = useState(0.0);
  const [showSystems, setShowSystems] = useState(true);
  const [clusterByDept, setClusterByDept] = useState(false);
  const [search, setSearch] = useState('');
  const [highlightId, setHighlightId] = useState<string | null>(null);
  const [selected, setSelected] = useState<{ id: string; label: string } | null>(null);

  const graph = useQuery({
    queryKey: ['graph', 'overview', minScore],
    queryFn: () => graphApi.overview(minScore, 250),
    refetchInterval: 30_000,
  });

  const matches = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return [] as string[];
    return (graph.data?.nodes ?? [])
      .filter((n) => n.id.toLowerCase().includes(q))
      .map((n) => n.id)
      .slice(0, 8);
  }, [graph.data, search]);

  const stats = useMemo(() => {
    const employees = (graph.data?.nodes ?? []).filter((n) => n.label === 'Employee');
    const systems = (graph.data?.nodes ?? []).filter((n) => n.label === 'System');
    const critical = employees.filter((n) => n.risk_level === 'CRITICAL').length;
    const high = employees.filter((n) => n.risk_level === 'HIGH').length;
    return {
      employees: employees.length,
      systems: systems.length,
      critical,
      high,
      edges: graph.data?.edges.length ?? 0,
    };
  }, [graph.data]);

  return (
    <div className="space-y-4">
      <header className="flex items-end justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-2xl font-semibold text-slate-100">Graph Explorer</h1>
          <p className="text-sm text-slate-400 mt-1">
            {stats.employees} employees · {stats.systems} systems · {stats.edges} edges
          </p>
        </div>
        <div className="flex gap-2 flex-wrap">
          <Toggle on={showSystems} onChange={setShowSystems} label="Show systems" />
          <Toggle on={clusterByDept} onChange={setClusterByDept} label="Cluster by dept" />
        </div>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_18rem] gap-4">
        <section className="panel p-2 overflow-hidden relative">
          {graph.isLoading ? (
            <Skeleton className="h-[540px] w-full" />
          ) : (
            <GraphCanvas
              data={graph.data ?? { nodes: [], edges: [] }}
              showSystems={showSystems}
              highlightId={highlightId}
              clusterByDepartment={clusterByDept}
              onSelectNode={(id, label) => setSelected({ id, label })}
            />
          )}
        </section>

        <aside className="space-y-3">
          {/* Search */}
          <div className="panel p-4">
            <h3 className="text-xs uppercase tracking-widest text-slate-400 mb-2">Search</h3>
            <div className="relative">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="EMP_xxxxxxxx"
                className="w-full bg-slate-900/50 border border-slate-800 rounded-lg pl-9 pr-3 py-1.5 text-sm focus:outline-none focus:border-accent transition-colors"
              />
            </div>
            {matches.length > 0 && (
              <div className="mt-2 space-y-1">
                {matches.map((id) => (
                  <button
                    key={id}
                    onClick={() => {
                      setHighlightId(id);
                      setSearch(id);
                    }}
                    className="w-full text-left text-xs font-mono px-2 py-1 rounded hover:bg-slate-800 text-slate-400 hover:text-slate-100 transition-colors"
                  >
                    {id}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Filters */}
          <div className="panel p-4">
            <h3 className="text-xs uppercase tracking-widest text-slate-400 mb-3">Min risk score</h3>
            <input
              type="range"
              min={0}
              max={0.2}
              step={0.01}
              value={minScore}
              onChange={(e) => setMinScore(Number(e.target.value))}
              className="w-full accent-accent"
            />
            <div className="flex justify-between text-[10px] font-mono text-slate-500 mt-1">
              <span>0.00</span>
              <span className="text-slate-200">{minScore.toFixed(2)}</span>
              <span>0.20</span>
            </div>
          </div>

          {/* Stats */}
          <div className="panel p-4 space-y-2">
            <h3 className="text-xs uppercase tracking-widest text-slate-400 mb-2">In view</h3>
            <Row label="CRITICAL" value={stats.critical} color="text-risk-critical" />
            <Row label="HIGH" value={stats.high} color="text-risk-high" />
            <Row label="Employees" value={stats.employees} />
            <Row label="Systems" value={stats.systems} />
          </div>

          {/* Selection */}
          {selected && (
            <div className="panel p-4">
              <h3 className="text-xs uppercase tracking-widest text-slate-400 mb-2">Selected</h3>
              <div className="font-mono text-sm text-slate-200">{selected.id}</div>
              <div className="text-xs text-slate-500 mb-3">{selected.label}</div>
              {selected.label === 'Employee' && (
                <Link
                  to={`/employees/${selected.id}`}
                  className="inline-block w-full text-center px-3 py-1.5 rounded-md bg-accent text-white text-xs hover:bg-accent2 transition-colors"
                >
                  Open detail
                </Link>
              )}
            </div>
          )}

          {/* Legend */}
          <div className="panel p-4 text-xs text-slate-400 space-y-2">
            <div className="font-mono uppercase tracking-widest text-slate-500 mb-2">Legend</div>
            <div className="flex items-center gap-2">
              <span className="h-3 w-3 rounded-full bg-risk-critical" /> CRITICAL employee
            </div>
            <div className="flex items-center gap-2">
              <span className="h-3 w-3 rounded-full bg-risk-high" /> HIGH employee
            </div>
            <div className="flex items-center gap-2">
              <span className="h-3 w-3 rounded-full bg-risk-medium" /> MEDIUM employee
            </div>
            <div className="flex items-center gap-2">
              <span className="h-3 w-3 rounded-full bg-risk-low" /> LOW / monitored
            </div>
            <div className="flex items-center gap-2">
              <span className="h-2.5 w-2.5 rounded-full bg-slate-600" /> System resource
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}

function Toggle({ on, onChange, label }: { on: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <button
      onClick={() => onChange(!on)}
      className={cn(
        'px-3 py-1 text-xs rounded-md border transition-colors',
        on
          ? 'bg-accent text-white border-accent'
          : 'bg-slate-900/30 text-slate-400 border-slate-800 hover:text-slate-100',
      )}
    >
      {label}
    </button>
  );
}

function Row({ label, value, color }: { label: string; value: number; color?: string }) {
  return (
    <div className="flex justify-between text-xs font-mono">
      <span className="text-slate-500">{label}</span>
      <span className={cn('text-slate-100', color)}>{value}</span>
    </div>
  );
}
