import { RISK_COLOR } from '@/lib/format';

/**
 * Animated SVG arc gauge for a 0–1 score. Color follows risk level.
 */
export function ScoreGauge({
  score,
  level,
  size = 160,
  label,
}: {
  score: number;
  level: string;
  size?: number;
  label?: string;
}) {
  const stroke = 12;
  const r = (size - stroke) / 2;
  const cx = size / 2;
  const cy = size / 2;
  const circumference = 2 * Math.PI * r;
  const clamped = Math.min(Math.max(score, 0), 1);
  const dash = circumference * clamped;
  const color = RISK_COLOR[level] ?? RISK_COLOR.LOW;

  return (
    <div className="relative flex flex-col items-center" style={{ width: size }}>
      <svg width={size} height={size} className="-rotate-90 overflow-visible">
        <circle cx={cx} cy={cy} r={r} fill="none" stroke="rgba(148,163,184,0.15)" strokeWidth={stroke} />
        <circle
          cx={cx}
          cy={cy}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference - dash}
          style={{
            transition: 'stroke-dashoffset 600ms ease, stroke 200ms ease',
            filter: `drop-shadow(0 0 8px ${color}44)`,
          }}
        />
      </svg>
      <div
        className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none"
        style={{ height: size }}
      >
        <span className="font-mono text-3xl font-semibold tracking-tight text-slate-50">
          {score.toFixed(2)}
        </span>
        <span className="text-[10px] uppercase tracking-widest text-slate-400 mt-1" style={{ color }}>
          {level}
        </span>
      </div>
      {label && (
        <span className="text-xs text-slate-500 uppercase tracking-widest mt-3">{label}</span>
      )}
    </div>
  );
}
