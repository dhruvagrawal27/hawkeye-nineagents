import { useState, useRef, useEffect } from 'react';
import { ChevronDown, ShieldCheck, User, Building2, type LucideIcon } from 'lucide-react';
import { ROLES, useRoleStore, type Role } from '@/store/roleStore';
import { cn } from '@/lib/format';

const ROLE_ICONS: Record<Role, LucideIcon> = {
  analyst: User,
  supervisor: ShieldCheck,
  manager: Building2,
};

export function RoleSwitcher() {
  const role = useRoleStore((s) => s.role);
  const setRole = useRoleStore((s) => s.setRole);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('click', onDoc);
    return () => document.removeEventListener('click', onDoc);
  }, []);

  const current = ROLES[role];
  const Icon = ROLE_ICONS[role];

  return (
    <div ref={ref} className="relative">
      <button
        onClick={(e) => {
          e.stopPropagation();
          setOpen((p) => !p);
        }}
        className="inline-flex items-center gap-1.5 px-2 py-1 rounded border border-line/60 bg-panel/60 hover:border-accent/40 hover:bg-panel transition-colors"
      >
        <Icon size={11} className="text-accent" />
        <span className="text-2xs font-mono uppercase tracking-widest text-ink">{current.label}</span>
        <ChevronDown size={11} className="text-dim" />
      </button>

      {open && (
        <div className="absolute right-0 top-[calc(100%+4px)] w-80 panel z-40 p-1.5">
          <div className="px-2 py-1 text-3xs uppercase tracking-widest text-dim border-b border-line/40 mb-1">
            Switch role · demo only
          </div>
          {(Object.values(ROLES) as typeof ROLES[Role][]).map((spec) => {
            const RIcon = ROLE_ICONS[spec.id];
            const active = spec.id === role;
            return (
              <button
                key={spec.id}
                onClick={() => {
                  setRole(spec.id);
                  setOpen(false);
                }}
                className={cn(
                  'w-full text-left px-2.5 py-2 rounded transition-colors flex items-start gap-2',
                  active ? 'bg-accent/15 text-ink' : 'hover:bg-line/40',
                )}
              >
                <RIcon size={14} className={active ? 'text-accent mt-0.5' : 'text-dim mt-0.5'} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-ink">{spec.label}</span>
                    {active && (
                      <span className="text-3xs font-mono text-accent uppercase tracking-widest">active</span>
                    )}
                  </div>
                  <div className="text-3xs font-mono text-dim mt-0.5">{spec.username}</div>
                  <div className="text-2xs text-dim mt-1 leading-relaxed">{spec.shortDescription}</div>
                </div>
              </button>
            );
          })}
          <div className="px-2 pt-1.5 mt-1 border-t border-line/40 text-3xs font-mono text-dim/80 leading-relaxed">
            In production, role is taken from the Keycloak JWT.
            This switcher is a local override for the demo.
          </div>
        </div>
      )}
    </div>
  );
}
