import { useMemo } from 'react';
import { format, parseISO } from 'date-fns';
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { ScorePoint } from '@/lib/api';

export function ScoreTimeline({ points }: { points: ScorePoint[] }) {
  const data = useMemo(
    () =>
      points.map((p) => ({
        ...p,
        ts: parseISO(p.recorded_at).getTime(),
        label: format(parseISO(p.recorded_at), 'MMM d'),
      })),
    [points],
  );

  if (data.length === 0) {
    return (
      <div className="text-sm text-slate-500 italic text-center py-12">
        No score history yet — replay a few minutes of activity to populate the timeline.
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={260}>
      <AreaChart data={data} margin={{ top: 10, right: 16, left: -10, bottom: 0 }}>
        <defs>
          <linearGradient id="risk-grad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#3B82F6" stopOpacity={0.4} />
            <stop offset="100%" stopColor="#3B82F6" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="2 4" stroke="#1e293b" />
        <XAxis
          dataKey="label"
          stroke="#475569"
          tick={{ fill: '#64748b', fontSize: 11 }}
          tickLine={false}
        />
        <YAxis
          domain={[0, 1]}
          stroke="#475569"
          tick={{ fill: '#64748b', fontSize: 11 }}
          tickLine={false}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: '#0F172A',
            border: '1px solid #334155',
            borderRadius: 8,
            color: '#e2e8f0',
            fontSize: 12,
          }}
          labelStyle={{ color: '#94a3b8' }}
          formatter={(v: number) => [v.toFixed(3), 'display']}
        />
        <Area
          type="monotone"
          dataKey="display_score"
          stroke="#3B82F6"
          strokeWidth={2}
          fill="url(#risk-grad)"
          dot={{ fill: '#3B82F6', r: 3 }}
          activeDot={{ r: 5 }}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
