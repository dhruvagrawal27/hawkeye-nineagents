import { formatDistanceToNowStrict, parseISO } from 'date-fns';

export function timeAgo(iso: string | Date | null | undefined): string {
  if (!iso) return '—';
  const d = typeof iso === 'string' ? parseISO(iso) : iso;
  try {
    return formatDistanceToNowStrict(d, { addSuffix: true });
  } catch {
    return '—';
  }
}

export function inr(value: number | null | undefined): string {
  if (value == null) return '—';
  const v = Math.abs(value);
  if (v >= 1e7) return `₹${(value / 1e7).toFixed(2)} Cr`;
  if (v >= 1e5) return `₹${(value / 1e5).toFixed(2)} L`;
  return `₹${value.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;
}

export function pct(value: number | null | undefined, digits = 1): string {
  if (value == null) return '—';
  return `${(value * 100).toFixed(digits)}%`;
}

export function cn(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(' ');
}

export const RISK_COLOR: Record<string, string> = {
  LOW:      '#10B981',
  MEDIUM:   '#F59E0B',
  HIGH:     '#F97316',
  CRITICAL: '#EF4444',
};

export const RISK_BADGE: Record<string, string> = {
  LOW:      'badge-low',
  MEDIUM:   'badge-medium',
  HIGH:     'badge-high',
  CRITICAL: 'badge-critical',
};
