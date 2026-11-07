type Props = { name: string; time: string; progress: number; label: string; size?: number };

/** A thin gold ring around the next prayer time, filling as it approaches. */
export function PrayerRing({ name, time, progress, label, size = 76 }: Props) {
  const p = Math.min(1, Math.max(0, Number.isFinite(progress) ? progress : 0));
  const stroke = 3;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  return (
    <div role="img" aria-label={label} className="relative shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90" aria-hidden="true">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--faint)" strokeWidth={stroke} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="var(--gold)"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - p)}
          data-testid="prayer-progress"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center leading-tight" aria-hidden="true">
        <span className="text-[11px] text-muted">{name}</span>
        <span className="text-sm font-medium tabular-nums text-gold-ink" dir="ltr">{time}</span>
      </div>
    </div>
  );
}
