import Link from "next/link";

type Props = { label: string; href?: string; state?: "idle" | "thinking"; size?: number };

/** Ahmad's gold orb. Breathes when idle, pulses while thinking; still when reduced motion is on. */
export function Orb({ label, href, state = "idle", size = 64 }: Props) {
  const style = { width: size, height: size };
  if (!href) {
    return <span className="orb inline-block rounded-full" data-state={state} style={style} aria-hidden="true" />;
  }
  return (
    <Link
      href={href}
      aria-label={label}
      className="orb block rounded-full ring-1 ring-gold/30 transition-transform active:scale-95"
      data-state={state}
      style={style}
    />
  );
}
