import { NavLink, Outlet } from 'react-router-dom';
import { Activity, AlertTriangle, BarChart3, GitBranch, Play, Settings, Users } from 'lucide-react';

const links = [
  { to: '/',           label: 'Dashboard',       icon: BarChart3 },
  { to: '/alerts',     label: 'Alerts',          icon: AlertTriangle },
  { to: '/employees',  label: 'Employees',       icon: Users },
  { to: '/graph',      label: 'Graph Explorer',  icon: GitBranch },
  { to: '/replay',     label: 'Replay Studio',   icon: Play },
  { to: '/settings',   label: 'Settings',        icon: Settings },
];

export function AppShell() {
  return (
    <div className="min-h-full grid grid-cols-[16rem_1fr] grid-rows-[auto_1fr]">
      {/* Sidebar */}
      <aside className="row-span-2 bg-panel/60 border-r border-slate-800 px-4 py-5 flex flex-col">
        <div className="flex items-center gap-2 mb-8">
          <span className="text-2xl font-bold tracking-tight text-accent">●</span>
          <span className="font-bold tracking-tight text-slate-100">HAWKEYE</span>
          <span className="text-[10px] uppercase tracking-widest text-slate-500 font-mono">v0.1</span>
        </div>
        <nav className="flex flex-col gap-1">
          {links.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                  isActive
                    ? 'bg-accent/15 text-accent border border-accent/40'
                    : 'text-slate-400 hover:bg-slate-800/40 hover:text-slate-100'
                }`
              }
            >
              <Icon size={16} />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto text-xs text-slate-500 font-mono pt-6 border-t border-slate-800">
          NINEAGENTS • RBI NFPC #4
        </div>
      </aside>

      {/* Top bar */}
      <header className="border-b border-slate-800 bg-panel/40 px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Activity size={16} className="text-accent animate-pulse" />
          <span className="text-sm text-slate-300">Real-time insider-fraud detection</span>
        </div>
        <span className="text-xs text-slate-500 font-mono">analyst@hawkeye.local</span>
      </header>

      {/* Page */}
      <main className="px-6 py-6 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  );
}
