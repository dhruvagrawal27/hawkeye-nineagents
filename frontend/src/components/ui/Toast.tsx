/**
 * Lightweight toast system with WebSocket integration.
 * Mounted once at the app root; subscribers push via the `toast()` API.
 */
import { create } from 'zustand';
import { useEffect } from 'react';
import { AlertTriangle, CheckCircle2, Info, X, type LucideIcon } from 'lucide-react';
import { cn } from '@/lib/format';

type Variant = 'info' | 'success' | 'alert' | 'critical';

interface ToastEntry {
  id: number;
  title: string;
  body?: string;
  variant: Variant;
  ttl: number;
  ts: number;
}

interface ToastStore {
  toasts: ToastEntry[];
  push: (t: Omit<ToastEntry, 'id' | 'ts'>) => void;
  dismiss: (id: number) => void;
}

export const useToastStore = create<ToastStore>((set) => ({
  toasts: [],
  push: (t) =>
    set((s) => ({
      toasts: [...s.toasts, { ...t, id: Date.now() + Math.random(), ts: Date.now() }],
    })),
  dismiss: (id) =>
    set((s) => ({ toasts: s.toasts.filter((x) => x.id !== id) })),
}));

export function toast(title: string, opts: { body?: string; variant?: Variant; ttl?: number } = {}) {
  useToastStore.getState().push({
    title,
    body: opts.body,
    variant: opts.variant ?? 'info',
    ttl: opts.ttl ?? 5000,
  });
}

const ICON: Record<Variant, LucideIcon> = {
  info: Info,
  success: CheckCircle2,
  alert: AlertTriangle,
  critical: AlertTriangle,
};

const VARIANT_CLASS: Record<Variant, string> = {
  info: 'border-slate-700 bg-panel/95',
  success: 'border-emerald-700 bg-emerald-950/80',
  alert: 'border-amber-700 bg-amber-950/80',
  critical: 'border-red-700 bg-red-950/80',
};

export function ToastViewport() {
  const { toasts, dismiss } = useToastStore();

  useEffect(() => {
    const timers = toasts.map((t) => {
      const remaining = t.ttl - (Date.now() - t.ts);
      return setTimeout(() => dismiss(t.id), Math.max(remaining, 0));
    });
    return () => {
      timers.forEach(clearTimeout);
    };
  }, [toasts, dismiss]);

  return (
    <div className="fixed bottom-5 right-5 z-50 flex flex-col gap-2 w-[28rem] max-w-[calc(100vw-2.5rem)]">
      {toasts.map((t) => {
        const Icon = ICON[t.variant];
        return (
          <div
            key={t.id}
            className={cn(
              'pointer-events-auto rounded-xl border px-4 py-3 shadow-xl backdrop-blur-md',
              'animate-in slide-in-from-right duration-300',
              VARIANT_CLASS[t.variant],
            )}
          >
            <div className="flex gap-3">
              <Icon size={18} />
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-slate-50">{t.title}</div>
                {t.body && <div className="text-xs text-slate-400 mt-0.5 leading-relaxed">{t.body}</div>}
              </div>
              <button
                onClick={() => dismiss(t.id)}
                className="text-slate-500 hover:text-slate-200 transition-colors"
              >
                <X size={14} />
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
