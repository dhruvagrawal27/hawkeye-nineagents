import { useEffect, useState } from 'react';
import { Area, AreaChart, ResponsiveContainer, Tooltip, YAxis } from 'recharts';
import { hawkeyeWs } from '@/lib/ws';

interface Bucket {
  t: number;          // bucket-start unix ms
  events: number;
  alerts: number;
}

const BUCKET_MS = 1000;        // 1-second buckets
const WINDOW_BUCKETS = 60;     // last 60 seconds

/**
 * Live events/sec chart fed by event.scored WS messages.
 * Smooths to 1-second buckets so the line breathes evenly.
 */
export function EventRateChart({ height = 110, showHeader = true }: { height?: number; showHeader?: boolean }) {
  const [buckets, setBuckets] = useState<Bucket[]>(() => seedEmpty());

  useEffect(() => {
    hawkeyeWs.connect();
    const unsub = hawkeyeWs.subscribe((msg) => {
      if (msg.type !== 'event.scored' && msg.type !== 'alert.new') return;
      const bucketStart = Math.floor(Date.now() / BUCKET_MS) * BUCKET_MS;
      setBuckets((prev) => {
        const last = prev[prev.length - 1];
        if (last && last.t === bucketStart) {
          const updated = { ...last };
          if (msg.type === 'event.scored') updated.events += 1;
          if (msg.type === 'alert.new')    updated.alerts += 1;
          return [...prev.slice(0, -1), updated];
        }
        return [...prev, { t: bucketStart, events: msg.type === 'event.scored' ? 1 : 0, alerts: msg.type === 'alert.new' ? 1 : 0 }];
      });
    });
    // Roll the window every second so empty seconds are still drawn
    const id = setInterval(() => {
      const cutoff = Math.floor(Date.now() / BUCKET_MS) * BUCKET_MS - WINDOW_BUCKETS * BUCKET_MS;
      setBuckets((prev) => {
        const trimmed = prev.filter((b) => b.t >= cutoff);
        const lastT = trimmed.length ? trimmed[trimmed.length - 1].t : cutoff;
        const nowT = Math.floor(Date.now() / BUCKET_MS) * BUCKET_MS;
        // Pad gaps with zero buckets so the line keeps moving
        const padded: Bucket[] = [...trimmed];
        for (let t = lastT + BUCKET_MS; t <= nowT; t += BUCKET_MS) {
          padded.push({ t, events: 0, alerts: 0 });
        }
        return padded.slice(-WINDOW_BUCKETS);
      });
    }, 1_000);
    return () => {
      unsub();
      clearInterval(id);
    };
  }, []);

  const total = buckets.reduce((s, b) => s + b.events, 0);
  const avgEps = total / Math.max(1, buckets.length);

  return (
    <div className="panel p-3">
      {showHeader && (
        <header className="flex items-center justify-between mb-2">
          <span className="eyebrow">Events / sec  ·  60s window</span>
          <span className="font-mono text-ink text-sm tabular-nums">
            {avgEps.toFixed(1)} <span className="text-dim text-2xs">avg</span>
          </span>
        </header>
      )}
      <div style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={buckets} margin={{ top: 4, right: 0, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="rate-grad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%"   stopColor="#22D3EE" stopOpacity={0.6} />
                <stop offset="100%" stopColor="#22D3EE" stopOpacity={0} />
              </linearGradient>
            </defs>
            <YAxis hide domain={[0, 'auto']} />
            <Tooltip
              cursor={false}
              contentStyle={{
                background: '#0B1024',
                border: '1px solid #1F2A4D',
                borderRadius: 6,
                fontSize: 11,
                fontFamily: 'JetBrains Mono, monospace',
                padding: '4px 8px',
              }}
              labelFormatter={() => ''}
              formatter={(v: number, name: string) => [v, name === 'events' ? 'ev/s' : 'alerts/s']}
            />
            <Area
              type="step"
              dataKey="events"
              stroke="#22D3EE"
              strokeWidth={1.4}
              fill="url(#rate-grad)"
              isAnimationActive={false}
              dot={false}
            />
            <Area
              type="step"
              dataKey="alerts"
              stroke="#F43F5E"
              strokeWidth={1.4}
              fill="rgba(244,63,94,0.15)"
              isAnimationActive={false}
              dot={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function seedEmpty(): Bucket[] {
  const now = Math.floor(Date.now() / BUCKET_MS) * BUCKET_MS;
  return Array.from({ length: WINDOW_BUCKETS }, (_, i) => ({
    t: now - (WINDOW_BUCKETS - i) * BUCKET_MS,
    events: 0,
    alerts: 0,
  }));
}
