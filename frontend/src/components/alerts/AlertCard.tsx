import { useEffect, useRef, useState } from 'react';
import { formatDistanceToNow, parseISO } from 'date-fns';
import type { Alert } from '@/lib/api';
import { cn } from '@/lib/format';

const levelClass: Record<Alert['risk_level'], string> = {
  LOW: 'badge-low',
  MEDIUM: 'badge-medium',
  HIGH: 'badge-high',
  CRITICAL: 'badge-critical',
};

const FLASH_MS = 1500;

export function AlertCard({ alert, onClick }: { alert: Alert; onClick?: () => void }) {
  // Flash on mount AND when score / triggered_at changes
  const seenRef = useRef<{ id: number; lastSeen: string; score: number }>({
    id: -1,
    lastSeen: '',
    score: -1,
  });
  const [fresh, setFresh] = useState(false);

  useEffect(() => {
    const prev = seenRef.current;
    const isNew = prev.id !== alert.id;
    const wasUpdated =
      prev.id === alert.id && (prev.lastSeen !== alert.last_seen_at || prev.score !== alert.score);

    if (isNew || wasUpdated) {
      setFresh(true);
      const t = setTimeout(() => setFresh(false), FLASH_MS);
      seenRef.current = { id: alert.id, lastSeen: alert.last_seen_at, score: alert.score };
      return () => clearTimeout(t);
    }
  }, [alert.id, alert.last_seen_at, alert.score]);

  const flashClass =
    alert.risk_level === 'CRITICAL'
      ? 'ring-2 ring-red-500/60 bg-red-950/40'
      : alert.risk_level === 'HIGH'
      ? 'ring-2 ring-orange-500/60 bg-orange-950/30'
      : alert.risk_level === 'MEDIUM'
      ? 'ring-2 ring-amber-500/50 bg-amber-950/20'
      : 'ring-2 ring-emerald-500/50 bg-emerald-950/20';

  return (
    <button
      onClick={onClick}
      className={cn(
        'panel w-full text-left px-4 py-3 transition-all',
        fresh ? flashClass : 'hover:border-accent/60',
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="font-mono text-xs text-slate-400">{alert.employee_id}</span>
            <span className={`badge ${levelClass[alert.risk_level]}`}>{alert.risk_level}</span>
          </div>
          <div className="text-sm text-slate-200">{alert.top_signal ?? 'Signal pending'}</div>
        </div>
        <div className="text-right shrink-0">
          <div className="font-mono text-2xl text-slate-50">{alert.display_score.toFixed(2)}</div>
          <div className="text-[10px] text-slate-500 font-mono">
            {formatDistanceToNow(parseISO(alert.triggered_at), { addSuffix: true })}
          </div>
        </div>
      </div>
    </button>
  );
}
