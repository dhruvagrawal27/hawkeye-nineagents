import { NavLink, Outlet } from 'react-router-dom';
import { AlertTriangle, BarChart3, Building2, GitBranch, Play, Settings, Users } from 'lucide-react';
import { TopStatusBar } from '@/components/layout/TopStatusBar';
import { useRole } from '@/store/roleStore';
import { cn } from '@/lib/format';

const ALL_LINKS = [
  { to: '/',           label: 'Command Center',  short: 'CMD',  icon: Building2,    managerOnly: true  },
  { to: '/dashboard',  label: 'Dashboard',       short: 'DASH', icon: BarChart3,    managerOnly: false },
  { to: '/alerts',     label: 'Alerts',          short: 'ALRT', icon: AlertTriangle, managerOnly: false },
  { to: '/employees',  label: 'Employees',       short: 'EMP',  icon: Users,         managerOnly: false },
  { to: '/graph',      label: 'Graph Explorer',  short: 'GRPH', icon: GitBranch,     managerOnly: false },
  { to: '/replay',     label: 'Replay Studio',   short: 'RPLY', icon: Play,          managerOnly: false },
  { to: '/settings',   label: 'Settings',        short: 'CFG',  icon: Settings,      managerOnly: false },
];

export function AppShell() {
  const role = useRole();

  // For non-managers, the index '/' renders Dashboard, so the Command Center
  // link in the sidebar is hidden. The Dashboard link stays as the default home.
  const links = role.canViewDepartmentRollup
    ? ALL_LINKS
    : ALL_LINKS.filter((l) => !l.managerOnly).map((l, i) => i === 0 ? { ...l, to: '/' } : l);

  return (
    <div className="min-h-full grid grid-rows-[auto_1fr]">
      <TopStatusBar />

      <div className="grid grid-cols-[13rem_1fr]">
        <aside className="bg-panel/50 border-r border-line/60 px-3 py-4 flex flex-col">
          <nav className="flex flex-col gap-0.5">
            {links.map(({ to, label, short, icon: Icon }) => (
              <NavLink
                key={to + label}
                to={to}
                end={to === '/'}
                className={({ isActive }) =>
                  cn(
                    'group flex items-center gap-3 px-2.5 py-1.5 rounded text-xs transition-colors border-l-2',
                    isActive
                      ? 'bg-accent/10 text-ink border-accent'
                      : 'border-transparent text-dim hover:bg-line/30 hover:text-ink',
                  )
                }
              >
                <Icon size={14} className="shrink-0" />
                <span className="font-mono uppercase tracking-widest text-3xs w-9 text-dim group-[.active]:text-accent">{short}</span>
                <span>{label}</span>
              </NavLink>
            ))}
          </nav>
          <div className="mt-auto pt-4 border-t border-line/60 text-3xs font-mono uppercase tracking-widest text-dim/80 leading-relaxed">
            NINEAGENTS
            <br />
            RBI NFPC #4
            <br />
            AUC 0.998 · F1 0.967
          </div>
        </aside>

        <main className="px-4 py-3 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
