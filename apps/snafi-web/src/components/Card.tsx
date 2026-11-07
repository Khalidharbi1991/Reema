import type { ReactNode } from "react";

type Props = { title: string; index?: number; badge?: ReactNode; children: ReactNode };

/** A quiet card that fades and rises in, staggered by index. */
export function Card({ title, index = 0, badge, children }: Props) {
  return (
    <section
      className="rise-in rounded-2xl border border-edge bg-card p-5 shadow-[0_1px_0_0_var(--faint)]"
      style={{ ["--i" as string]: index }}
      aria-label={title}
    >
      <header className="mb-3 flex items-center justify-between gap-3">
        <h2 className="text-lg text-gold-ink">{title}</h2>
        {badge}
      </header>
      {children}
    </section>
  );
}

export function PlaceholderBadge({ label }: { label: string }) {
  return (
    <span className="rounded-full border border-edge px-2 py-0.5 text-[10px] uppercase tracking-[0.14em] text-muted" data-placeholder="true">
      {label}
    </span>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`skeleton ${className}`} aria-hidden="true" />;
}
