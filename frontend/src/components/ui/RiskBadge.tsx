import { cn, RISK_BADGE } from '@/lib/format';

export function RiskBadge({ level, size = 'sm' }: { level: string; size?: 'sm' | 'md' }) {
  const cls = RISK_BADGE[level] ?? 'badge-low';
  return (
    <span className={cn('badge', cls, size === 'md' && 'px-3 py-1 text-sm')}>{level}</span>
  );
}
