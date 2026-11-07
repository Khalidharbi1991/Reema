import type { ComponentProps } from "react";
import { Menu } from "./Menu";

type Props = { appName: string } & ComponentProps<typeof Menu>;

/** Wordmark at the inline start, menu at the inline end (mirrors in Arabic). */
export function TopBar({ appName, ...menu }: Props) {
  return (
    <header className="flex items-center justify-between px-5 pt-[max(env(safe-area-inset-top),1rem)] pb-2">
      <span className="font-heading text-2xl tracking-[0.08em] text-gold-ink">{appName}</span>
      <Menu {...menu} />
    </header>
  );
}
