import { RISK_STYLES } from "@/lib/constants";
import { classNames } from "@/lib/format";
import type { RiskLevel } from "@/lib/types";

/**
 * The headline number as a 240° arc.
 *
 * An arc rather than a bar because the score is a single verdict, not a
 * comparison — and it reads at a glance on a phone, which is where an older
 * adult is most likely to open this.
 */
export function RiskGauge({
  score,
  level,
  size = 176,
}: {
  score: number;
  level: RiskLevel;
  size?: number;
}) {
  const style = RISK_STYLES[level];
  const stroke = 12;
  const radius = (size - stroke) / 2;
  const sweep = 240;
  const circumference = 2 * Math.PI * radius;
  const trackLength = (sweep / 360) * circumference;
  const filled = (Math.max(0, Math.min(100, score)) / 100) * trackLength;

  return (
    <div
      className="relative inline-flex items-center justify-center"
      style={{ width: size, height: size }}
      role="img"
      aria-label={`Scam risk score ${Math.round(score)} out of 100, rated ${level}`}
    >
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        style={{ transform: `rotate(${90 + (360 - sweep) / 2}deg)` }}
      >
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth={stroke}
          strokeLinecap="round"
          className="stroke-slate-700/40"
          strokeDasharray={`${trackLength} ${circumference}`}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth={stroke}
          strokeLinecap="round"
          className={classNames(style.stroke, "transition-[stroke-dasharray] duration-700")}
          strokeDasharray={`${filled} ${circumference}`}
        />
      </svg>

      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className={classNames("text-4xl font-bold tabular-nums", style.text)}>
          {Math.round(score)}
        </span>
        <span className="text-[11px] font-medium uppercase tracking-[0.14em] text-slate-500">
          out of 100
        </span>
      </div>
    </div>
  );
}
