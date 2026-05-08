import { useEffect } from 'react';
import { X } from 'lucide-react';
import { cn } from '@/lib/format';

interface SlideOverProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  subtitle?: string;
  children?: React.ReactNode;
  width?: 'narrow' | 'wide';
}

export function SlideOver({ open, onClose, title, subtitle, children, width = 'narrow' }: SlideOverProps) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    if (open) document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  return (
    <div
      className={cn(
        'fixed inset-0 z-40 transition-opacity',
        open ? 'pointer-events-auto opacity-100' : 'pointer-events-none opacity-0',
      )}
    >
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />
      <aside
        className={cn(
          'absolute right-0 top-0 h-full bg-panel border-l border-slate-800 shadow-2xl shadow-black/50 transition-transform overflow-y-auto',
          width === 'narrow' ? 'w-[28rem]' : 'w-[44rem]',
          open ? 'translate-x-0' : 'translate-x-full',
        )}
      >
        <header className="sticky top-0 bg-panel/95 backdrop-blur z-10 border-b border-slate-800 px-6 py-4 flex items-start justify-between">
          <div>
            {title && <h2 className="text-lg font-semibold text-slate-100">{title}</h2>}
            {subtitle && <p className="text-xs text-slate-400 mt-0.5 font-mono">{subtitle}</p>}
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-100 -m-1 p-1 transition-colors"
          >
            <X size={20} />
          </button>
        </header>
        <div className="px-6 py-5">{children}</div>
      </aside>
    </div>
  );
}
