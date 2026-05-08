import { useEffect, useState } from 'react';
import { Play, Square, Zap } from 'lucide-react';
import { replayApi } from '@/lib/api';
import { LiveEventTicker } from '@/components/replay/LiveEventTicker';
import { toast } from '@/components/ui/Toast';

export function ReplayStudio() {
  const [status, setStatus] = useState<string>('idle');
  const [stats, setStats] = useState<Record<string, any>>({});
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const s = await replayApi.status();
        setStatus(s.status);
        setStats(s.stats ?? {});
      } catch {
        // ignore
      }
    };
    fetchStatus();
    const id = setInterval(fetchStatus, 1_500);
    return () => clearInterval(id);
  }, []);

  const start = async () => {
    setBusy(true);
    try {
      const r = await replayApi.start('mule_burst', 500);
      const dismissed = (r as any)?.alerts_dismissed ?? 0;
      toast(`Replay started`, {
        body: dismissed > 0 ? `Auto-dismissed ${dismissed} prior replay alerts` : undefined,
        variant: 'success',
      });
    } finally {
      setBusy(false);
    }
  };
  const stop = async () => {
    setBusy(true);
    try {
      await replayApi.stop();
      toast('Replay stopped', { variant: 'info' });
    } finally {
      setBusy(false);
    }
  };
  const burst = async () => {
    setBusy(true);
    try {
      const r = await replayApi.injectBurst();
      toast(`Injected ${r.published ?? 0} mule events`, { variant: 'alert' });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-slate-100">Replay Studio</h1>
        <p className="text-sm text-slate-400 mt-1">
          Stream the synthetic event log through Kafka into the scoring pipeline.{' '}
          <code className="font-mono text-accent">mule_burst</code> mode front-loads events from top
          mule accounts so alerts fire within 30–60 seconds.
        </p>
      </header>

      {/* Controls + stats row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="panel p-5 lg:col-span-2">
          <header className="flex items-center justify-between mb-4">
            <span className="text-sm uppercase tracking-wider text-slate-400">Playback</span>
            <StatusPill status={status} />
          </header>
          <div className="flex gap-3 flex-wrap">
            <button
              disabled={busy || status === 'running'}
              onClick={start}
              className="px-4 py-2 rounded-lg bg-accent text-white font-medium hover:bg-accent2 disabled:opacity-40 flex items-center gap-2 transition-colors"
            >
              <Play size={16} /> Start mule_burst
            </button>
            <button
              disabled={busy || status !== 'running'}
              onClick={stop}
              className="px-4 py-2 rounded-lg bg-slate-700 text-white hover:bg-slate-600 disabled:opacity-40 flex items-center gap-2 transition-colors"
            >
              <Square size={16} /> Stop
            </button>
            <button
              disabled={busy}
              onClick={burst}
              className="px-4 py-2 rounded-lg bg-amber-600 text-white hover:bg-amber-500 disabled:opacity-40 flex items-center gap-2 transition-colors"
            >
              <Zap size={16} /> Inject mule burst
            </button>
          </div>
        </div>

        <div className="panel p-5">
          <span className="text-sm uppercase tracking-wider text-slate-400">Live counters</span>
          <div className="mt-3 space-y-2 text-sm font-mono">
            <Counter label="events published" value={stats.events_published} accent />
            <Counter label="alerts fired" value={stats.alerts_fired} accent />
            <Counter label="rate (ev/s)" value={stats.rate} />
            <Counter label="mode" value={stats.mode} />
          </div>
        </div>
      </div>

      {/* Live event tape */}
      <LiveEventTicker height={520} />
    </div>
  );
}

function StatusPill({ status }: { status: string }) {
  const isRunning = status === 'running';
  return (
    <span
      className={`badge ${
        isRunning
          ? 'bg-emerald-900/50 text-emerald-300 border border-emerald-700 animate-pulse'
          : 'bg-slate-800/60 text-slate-400 border border-slate-700'
      }`}
    >
      ● {status}
    </span>
  );
}

function Counter({
  label,
  value,
  accent,
}: {
  label: string;
  value?: any;
  accent?: boolean;
}) {
  return (
    <div className="flex justify-between items-baseline">
      <span className="text-slate-500">{label}</span>
      <span
        key={String(value ?? '')}
        className={
          accent
            ? 'text-slate-50 text-base tabular-nums animate-in fade-in slide-in-from-right-2 duration-150'
            : 'text-slate-300'
        }
      >
        {value ?? '—'}
      </span>
    </div>
  );
}
