import { useMemo } from 'react';

interface HourlyRow {
  hour: string; // ISO timestamp at hour boundary
  LOW: number;
  MEDIUM: number;
  HIGH: number;
  CRITICAL: number;
  total: number;
}

const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

/**
 * 7-day × 24-hour grid. Cell intensity = total alerts for that (day-of-week, hour-of-day) bucket.
 * Pure SVG, no D3.
 */
export function AlertHeatmap({ data }: { data: HourlyRow[] }) {
  const grid = useMemo(() => {
    const matrix: number[][] = Array.from({ length: 7 }, () => Array(24).fill(0));
    for (const row of data) {
      const d = new Date(row.hour);
      matrix[d.getDay()][d.getHours()] += row.total;
    }
    const max = Math.max(1, ...matrix.flat());
    return { matrix, max };
  }, [data]);

  const cellW = 18;
  const cellH = 14;
  const labelW = 32;
  const labelH = 18;
  const totalW = labelW + cellW * 24;
  const totalH = labelH + cellH * 7;

  return (
    <div className="overflow-x-auto">
      <svg width={totalW} height={totalH} className="block">
        {/* Hour labels (top) */}
        {Array.from({ length: 24 }).map((_, h) => (
          <text
            key={h}
            x={labelW + h * cellW + cellW / 2}
            y={labelH - 6}
            fontSize={9}
            textAnchor="middle"
            fill="#7A85AA"
            fontFamily="JetBrains Mono"
          >
            {h % 3 === 0 ? String(h).padStart(2, '0') : ''}
          </text>
        ))}
        {/* Day rows */}
        {grid.matrix.map((row, d) => (
          <g key={d}>
            <text
              x={labelW - 6}
              y={labelH + d * cellH + cellH / 2 + 3}
              fontSize={9}
              textAnchor="end"
              fill="#7A85AA"
              fontFamily="JetBrains Mono"
            >
              {DAYS[d]}
            </text>
            {row.map((v, h) => {
              const intensity = v / grid.max;
              const fill = v === 0 ? 'rgba(31,42,77,0.3)' : `rgba(244, 63, 94, ${0.15 + intensity * 0.85})`;
              return (
                <rect
                  key={h}
                  x={labelW + h * cellW + 1}
                  y={labelH + d * cellH + 1}
                  width={cellW - 2}
                  height={cellH - 2}
                  fill={fill}
                  rx={2}
                >
                  <title>{`${DAYS[d]} ${String(h).padStart(2, '0')}:00 — ${v} alert${v === 1 ? '' : 's'}`}</title>
                </rect>
              );
            })}
          </g>
        ))}
      </svg>
    </div>
  );
}
