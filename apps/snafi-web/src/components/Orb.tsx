import Link from "next/link";

type Props = { label: string; href?: string; state?: "idle" | "thinking" | "still"; size?: number };

/**
 * Ahmad's gold orb. Breathes when idle (Today and Sign-in), pulses while thinking, and is still
 * in the Chat bar otherwise; always still when reduced motion is on.
 */
export function Orb({ label, href, state = "idle", size = 64 }: Props) {
  const style = { width: size, height: size };
  if (!href) {
    return <span className="orb inline-block flex-none rounded-full" data-state={state} style={style} aria-hidden="true" />;
  }
  return (
    <Link
      href={href}
      aria-label={label}
      className="orb block rounded-full transition-transform active:scale-95"
      data-state={state}
      style={style}
    />
  );
}
